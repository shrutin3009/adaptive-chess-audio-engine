"""Flask app: serves the game page and the move-analysis / bot-move JSON API."""

from __future__ import annotations

import os
from typing import Any, Optional

import chess
import chess.engine
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

from chess_audio import config, engine
from chess_audio.bot_levels import BOT_LEVELS, apply_bot_level, normalize_difficulty, reset_engine_strength
from chess_audio.game_phase import detect_game_phase, game_phase_details
from chess_audio.move_classifier import classify_move
from chess_audio.opening_book import is_book_move

app = Flask(
    __name__,
    static_folder=str(config.PROJECT_ROOT / "static"),
    static_url_path="/static",
    template_folder=str(config.PROJECT_ROOT / "templates"),
)
CORS(app)


class ApiError(Exception):
    """An error returned to the client as {"error": message} with the given HTTP status."""

    def __init__(self, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


@app.errorhandler(ApiError)
def _api_error(error: ApiError):
    return jsonify({"error": error.message}), error.status


@app.errorhandler(FileNotFoundError)
def _engine_missing(error: FileNotFoundError):
    return jsonify({"error": str(error)}), 500


@app.errorhandler(chess.engine.EngineError)
def _engine_failed(error: chess.engine.EngineError):
    return jsonify({"error": f"Engine error: {error}"}), 500


def _parse_board(fen: Any) -> chess.Board:
    try:
        return chess.Board(fen)
    except ValueError as e:
        raise ApiError(f"Invalid FEN: {e}")


def _board_from_fen_field(data: dict) -> tuple[str, chess.Board]:
    fen = data.get("fen")
    if not fen or not isinstance(fen, str):
        raise ApiError("Missing or invalid 'fen'")
    return fen, _parse_board(fen)


def root_eval_delta(eval_before: int, eval_after: int, mover: str) -> int:
    """Root eval change from the mover's side. Misleading for move quality; exposed for debugging only."""
    if mover == "w":
        return eval_after - eval_before
    return eval_before - eval_after


def cp_loss_vs_best_continuation(
    board_before: chess.Board,
    best_uci: str,
    eval_after_played: int,
    mover: str,
    stockfish: chess.engine.SimpleEngine,
) -> tuple[float, int]:
    """
    Centipawn loss comparing the position after the engine's best move with the position after
    the played move (both White POV). Positive means the played move is worse for the mover.
    Returns (loss_cp, eval_after_best).
    """
    best_move = chess.Move.from_uci(best_uci)
    if best_move not in board_before.legal_moves:
        raise chess.IllegalMoveError(f"Engine best move illegal: {best_uci!r}")

    board_after_best = board_before.copy()
    board_after_best.push(best_move)
    eval_after_best = int(engine.evaluate_white_cp(board_after_best, stockfish)["eval_cp"])

    if mover == "w":
        loss = float(eval_after_best - eval_after_played)
    else:
        loss = float(eval_after_played - eval_after_best)
    return loss, eval_after_best


def infer_played_uci(board_before: chess.Board, board_after: chess.Board) -> Optional[str]:
    """Recover the move that turns board_before into board_after."""
    for move in board_before.legal_moves:
        trial = board_before.copy()
        trial.push(move)
        if trial.fen() == board_after.fen():
            return move.uci()
    return None


@app.route("/")
def index():
    return render_template("index.html")


@app.post("/api/evaluate")
def api_evaluate():
    """Evaluate one position. Body: {"fen": "..."}."""
    fen, board = _board_from_fen_field(request.get_json(silent=True) or {})
    with engine.engine_lock:
        evaluation = engine.evaluate_white_cp(board, engine.get_engine())
    return jsonify(
        {
            "fen": fen,
            "eval_cp": evaluation["eval_cp"],
            "mate": evaluation["mate"],
            "mate_in": evaluation["mate_in"],
        }
    )


@app.post("/api/bot-move")
def api_bot_move():
    """Pick the bot's move at the requested strength. Body: {"fen": "...", "difficulty": "medium"}."""
    data = request.get_json(silent=True) or {}
    _, board = _board_from_fen_field(data)
    if board.is_game_over():
        raise ApiError("No moves — game is over")

    requested_difficulty = data.get("difficulty", "medium")
    difficulty = normalize_difficulty(requested_difficulty if isinstance(requested_difficulty, str) else "medium")

    with engine.engine_lock:
        try:
            stockfish = engine.get_engine()
            result = stockfish.play(board, apply_bot_level(stockfish, difficulty))
        finally:
            # The engine is shared with analysis, which must always run at full strength.
            try:
                reset_engine_strength(engine.get_engine())
            except (FileNotFoundError, chess.engine.EngineError):
                pass

    if result is None or result.move is None:
        raise ApiError("Engine returned no move", 500)

    return jsonify(
        {
            "uci": result.move.uci(),
            "difficulty": difficulty,
            "bot_level": BOT_LEVELS[difficulty].get("label"),
        }
    )


def _read_move_request(data: dict) -> tuple[str, str, chess.Board, chess.Board, str, str]:
    """Validate an analyze-move body; returns (fen_before, fen_after, board_before, board_after, mover, played_uci)."""
    fen_before = data.get("fen_before")
    fen_after = data.get("fen_after")
    if not fen_before or not fen_after:
        raise ApiError("Need fen_before and fen_after")
    board_before = _parse_board(fen_before)
    board_after = _parse_board(fen_after)

    mover = fen_before.split()[1]
    if mover not in ("w", "b"):
        raise ApiError("Could not read side to move from fen_before")

    played_uci = data.get("played_uci")
    if not played_uci or not isinstance(played_uci, str):
        played_uci = infer_played_uci(board_before, board_after)
    if not played_uci:
        raise ApiError("Could not infer played_uci; pass played_uci from client")
    return fen_before, fen_after, board_before, board_after, mover, played_uci


def _analyze_move(
    fen_before: str,
    fen_after: str,
    board_before: chess.Board,
    board_after: chess.Board,
    mover: str,
    played_uci: str,
    stockfish: chess.engine.SimpleEngine,
) -> dict[str, Any]:
    eval_before = engine.evaluate_white_cp(board_before, stockfish)
    eval_after, mate_after = engine.evaluate_after_move(board_after, stockfish, mover)
    lines = engine.principal_lines(board_before, stockfish, config.MULTIPV_LINES)
    top_uci = [line.uci for line in lines[: max(1, config.MULTIPV_LINES)]]

    best_uci = top_uci[0] if top_uci else None
    if not best_uci:
        raise ApiError("Engine returned no principal variation", 500)

    # The second-best line feeds the "brilliant sacrifice" heuristic.
    second_line_cp = lines[1].white_cp if len(lines) > 1 else None

    classification, cp_loss, classifier_debug = classify_move(
        fen_before,
        played_uci,
        int(eval_before["eval_cp"]),
        int(eval_after["eval_cp"]),
        best_uci,
        second_line_cp,
    )

    phase_before = detect_game_phase(board_before)
    is_opening_book_move = phase_before == "opening" and is_book_move(board_before, played_uci)

    if board_after.is_checkmate():
        classification = "checkmate"
    elif is_opening_book_move:
        classification = "book"

    eval_after_played: Optional[int] = int(eval_after["eval_cp"])
    try:
        cp_loss_vs_best, eval_after_best = cp_loss_vs_best_continuation(
            board_before, best_uci, eval_after_played, mover, stockfish
        )
    except chess.IllegalMoveError:
        cp_loss_vs_best, eval_after_best, eval_after_played = None, None, None

    phase_after = game_phase_details(board_after)

    return {
        "fen_before": fen_before,
        "fen_after": fen_after,
        "mover": mover,
        "played_uci": played_uci,
        "best_uci": best_uci,
        "top_moves_uci": top_uci,
        "eval_before_cp": eval_before["eval_cp"],
        "eval_after_cp": eval_after["eval_cp"],
        "eval_best_child_cp": eval_after_best,
        "eval_played_child_cp": eval_after_played,
        "cp_loss_eye_on_chess": round(cp_loss, 2),
        "cp_loss_vs_best": round(cp_loss_vs_best, 2) if cp_loss_vs_best is not None else None,
        "next_best_eval_white": second_line_cp,
        "classifier": "eye-on-chess (amiwrpremium/eye-on-chess classify.ts)",
        "classifier_debug": classifier_debug,
        "delta_cp": root_eval_delta(eval_before["eval_cp"], eval_after["eval_cp"], mover),
        "classification": classification,
        "phase_before_move": phase_before,
        "is_book_move": is_opening_book_move,
        "opening_book_path": config.OPENING_BOOK_PATH,
        "book_debug": {
            "opening_book_path": config.OPENING_BOOK_PATH,
            "opening_book_path_exists": os.path.isfile(config.OPENING_BOOK_PATH),
        },
        "game_phase": phase_after["phase"],
        "game_phase_detail": phase_after,
        "mate_before": eval_before["mate"],
        "mate_after": eval_after["mate"],
        "is_checkmate_on_board": board_after.is_checkmate(),
        "is_mate_sequence": mate_after["is_mate_sequence"],
        "mate_in": mate_after["mate_in"],
        "mate_for_mover": mate_after["mate_for_mover"],
        "mate_score_pov_debug": mate_after.get("mate_score_pov_repr"),
    }


@app.post("/api/analyze-move")
def api_analyze_move():
    """
    Classify a played move. Body: {"fen_before": "...", "fen_after": "...", "played_uci": "e2e4"}
    (played_uci is optional and inferred from the two positions when omitted).
    """
    move_request = _read_move_request(request.get_json(silent=True) or {})
    with engine.engine_lock:
        return jsonify(_analyze_move(*move_request, engine.get_engine()))
