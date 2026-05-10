"""
Local Flask API: Stockfish position evaluation and move classification.
Set STOCKFISH_PATH to your Stockfish binary (defaults to a common Mac path).
"""

from __future__ import annotations

import os
import atexit
import threading
from typing import Any, Optional

import chess
import chess.engine
from flask import Flask, abort, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

from eye_on_chess_classify import classify_move_eye_on_chess, next_best_eval_white_from_multipv
from game_phase import detect_game_phase, detect_game_phase_debug
from opening_book import OPENING_BOOK_PATH, is_book_move
from bot_levels import BOT_LEVELS, apply_bot_level, normalize_difficulty, reset_engine_strength

MULTIPV_LINES = int(os.environ.get("MULTIPV_LINES", "10"))

# Override with: export STOCKFISH_PATH=/path/to/stockfish
STOCKFISH_PATH = os.environ.get(
    "STOCKFISH_PATH",
    "stockfish",
)

# Analysis depth (higher = slower, stronger)
ENGINE_DEPTH = int(os.environ.get("ENGINE_DEPTH", "12"))

app = Flask(__name__, static_folder="static", static_url_path="/static")
CORS(app)

_ROOT = os.path.dirname(os.path.abspath(__file__))
# Folder name in git is ``Sounds/`` (capital S); match it so Linux clones resolve correctly.
_SOUNDS_ROOT = os.path.join(_ROOT, "Sounds")


@app.route("/Sounds/<path:filename>")
@app.route("/sounds/<path:filename>")
def serve_project_sounds(filename: str):
    """Serve files from repo-root ``Sounds/`` (e.g. ``Sounds/Medium/ambience.wav``). Both ``/Sounds/`` and legacy ``/sounds/`` URLs work."""
    if not os.path.isdir(_SOUNDS_ROOT):
        abort(404)
    return send_from_directory(_SOUNDS_ROOT, filename)

_engine: Optional[chess.engine.SimpleEngine] = None
# One UCI process — all commands must be serialized (threaded WSGI / overlapping fetches).
_ENGINE_LOCK = threading.Lock()


def get_engine() -> chess.engine.SimpleEngine:
    global _engine
    if _engine is None:
        if not os.path.isfile(STOCKFISH_PATH):
            raise FileNotFoundError(
                f"Stockfish not found at {STOCKFISH_PATH!r}. "
                "Set the STOCKFISH_PATH environment variable."
            )
        _engine = chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)
    return _engine


def close_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.quit()
        _engine = None


atexit.register(close_engine)


def eval_white_cp(board: chess.Board, engine: chess.engine.SimpleEngine) -> dict[str, Any]:
    """Return evaluation from White's point of view (centipawns). Mate scores are large."""
    info = engine.analyse(board, chess.engine.Limit(depth=ENGINE_DEPTH))
    pov = info["score"].white()
    if pov.is_mate():
        m = pov.mate()
        # Mate score: positive = White mates; negative = Black mates
        cp = 10000 if m and m > 0 else -10000
        return {"eval_cp": cp, "mate": True, "mate_in": m}
    cp = pov.score()
    if cp is None:
        return {"eval_cp": 0, "mate": False, "mate_in": None}
    return {"eval_cp": cp, "mate": False, "mate_in": None}


def eval_white_cp_and_mover_mate_pov(
    board_after_move: chess.Board,
    engine: chess.engine.SimpleEngine,
    mover: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    One Stockfish analysis of the position after the move: White-POV eval (for existing logic)
    plus mate distance from the mover's POV (score.pov(mover_color); Stockfish mate scores only).
    """
    info = engine.analyse(board_after_move, chess.engine.Limit(depth=ENGINE_DEPTH))
    w = info["score"].white()
    if w.is_mate():
        m = w.mate()
        cp = 10000 if m and m > 0 else -10000
        ev = {"eval_cp": cp, "mate": True, "mate_in": m}
    else:
        cp = w.score()
        ev = {
            "eval_cp": int(cp) if cp is not None else 0,
            "mate": False,
            "mate_in": None,
        }

    mover_color = chess.WHITE if mover == "w" else chess.BLACK
    score = info["score"].pov(mover_color)
    if score.is_mate():
        mate_in = score.mate()
        mate_extra: dict[str, Any] = {
            "is_mate_sequence": True,
            "mate_in": mate_in,
            "mate_for_mover": mate_in is not None and mate_in > 0,
            "mate_score_pov_repr": repr(score),
        }
    else:
        mate_extra = {
            "is_mate_sequence": False,
            "mate_in": None,
            "mate_for_mover": False,
            "mate_score_pov_repr": repr(score),
        }
    return ev, mate_extra


def mover_delta_cp(eval_before: int, eval_after: int, mover: str) -> int:
    """Root eval delta (before vs after move). Misleading for quality; exposed for debugging only."""
    if mover == "w":
        return eval_after - eval_before
    return eval_before - eval_after


def cp_loss_vs_best_continuation(
    board_before: chess.Board,
    board_after: chess.Board,
    best_uci: str,
    mover: str,
    engine: chess.engine.SimpleEngine,
) -> tuple[float, int, int]:
    """
    Stockfish-style centipawn loss: compare resulting positions after best vs after played
    (both evaluated White POV). Positive = played line is worse for the mover.
    Returns (loss_cp, eval_white_after_best, eval_white_after_played).
    """
    m_best = chess.Move.from_uci(best_uci)
    if m_best not in board_before.legal_moves:
        raise chess.IllegalMoveError(f"Engine best move illegal: {best_uci!r}")

    b_best = board_before.copy()
    b_best.push(m_best)

    ev_best = eval_white_cp(b_best, engine)
    ev_played = eval_white_cp(board_after, engine)

    w_b = int(ev_best["eval_cp"])
    w_p = int(ev_played["eval_cp"])

    if mover == "w":
        loss = float(w_b - w_p)
    else:
        loss = float(w_p - w_b)

    return loss, w_b, w_p


def infer_played_uci(board_before: chess.Board, board_after: chess.Board) -> Optional[str]:
    """Recover UCI of the move that transforms board_before into board_after."""
    for move in board_before.legal_moves:
        trial = board_before.copy()
        trial.push(move)
        if trial.fen() == board_after.fen():
            return move.uci()
    return None


def multipv_root_uci(
    board: chess.Board, engine: chess.engine.SimpleEngine, lines: int
) -> list[str]:
    """Root moves from MultiPV (ordered best-first)."""
    infos = engine.analyse(
        board,
        chess.engine.Limit(depth=ENGINE_DEPTH),
        multipv=max(1, lines),
    )
    if not isinstance(infos, list):
        infos = [infos]
    out: list[str] = []
    for info in infos:
        pv = info.get("pv") or []
        if pv:
            out.append(pv[0].uci())
        else:
            out.append("")
    return out


@app.route("/")
def index():
    # Must use render_template so Jinja runs (url_for → real /static/app.js path).
    # send_from_directory would send raw HTML and break the chessboard script load.
    return render_template("index.html")


@app.post("/api/evaluate")
def api_evaluate():
    """
    Minimal endpoint: single FEN -> evaluation (for testing Stockfish wiring).
    Body: {"fen": "..."}
    """
    data = request.get_json(silent=True) or {}
    fen = data.get("fen")
    if not fen or not isinstance(fen, str):
        return jsonify({"error": "Missing or invalid 'fen'"}), 400
    try:
        board = chess.Board(fen)
    except ValueError as e:
        return jsonify({"error": f"Invalid FEN: {e}"}), 400
    try:
        with _ENGINE_LOCK:
            engine = get_engine()
            ev = eval_white_cp(board, engine)
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 500
    except chess.engine.EngineError as e:
        return jsonify({"error": f"Engine error: {e}"}), 500

    return jsonify(
        {
            "fen": fen,
            "eval_cp": ev["eval_cp"],
            "mate": ev["mate"],
            "mate_in": ev["mate_in"],
        }
    )


@app.post("/api/bot-move")
def api_bot_move():
    """
    Best move for the side to move on this FEN, using Stockfish with BOT_LEVELS[difficulty].
    Body: {"fen": "...", "difficulty": "medium"}
    """
    data = request.get_json(silent=True) or {}
    fen = data.get("fen")
    difficulty = data.get("difficulty", "medium")
    if not fen or not isinstance(fen, str):
        return jsonify({"error": "Missing or invalid 'fen'"}), 400
    try:
        board = chess.Board(fen)
    except ValueError as e:
        return jsonify({"error": f"Invalid FEN: {e}"}), 400
    if board.is_game_over():
        return jsonify({"error": "No moves — game is over"}), 400

    diff_key = normalize_difficulty(difficulty if isinstance(difficulty, str) else "medium")

    result: Any = None
    with _ENGINE_LOCK:
        try:
            engine = get_engine()
            limit = apply_bot_level(engine, diff_key)
            result = engine.play(board, limit)
        except FileNotFoundError as e:
            return jsonify({"error": str(e)}), 500
        except chess.engine.EngineError as e:
            return jsonify({"error": f"Engine error: {e}"}), 500
        finally:
            try:
                reset_engine_strength(get_engine())
            except (FileNotFoundError, chess.engine.EngineError):
                pass

    if result is None or result.move is None:
        return jsonify({"error": "Engine returned no move"}), 500

    return jsonify(
        {
            "uci": result.move.uci(),
            "difficulty": diff_key,
            "bot_level": BOT_LEVELS[diff_key].get("label"),
        }
    )


@app.post("/api/analyze-move")
def api_analyze_move():
    """
    Eval swing + MultiPV vs played move → classification.
    Body: {"fen_before": "...", "fen_after": "...", "played_uci": "e2e4" (optional)}
    """
    data = request.get_json(silent=True) or {}
    fen_before = data.get("fen_before")
    fen_after = data.get("fen_after")
    played_uci = data.get("played_uci")
    if not fen_before or not fen_after:
        return jsonify({"error": "Need fen_before and fen_after"}), 400
    try:
        board_before = chess.Board(fen_before)
        board_after = chess.Board(fen_after)
    except ValueError as e:
        return jsonify({"error": f"Invalid FEN: {e}"}), 400

    mover = fen_before.split()[1]
    if mover not in ("w", "b"):
        return jsonify({"error": "Could not read side to move from fen_before"}), 400

    if not played_uci or not isinstance(played_uci, str):
        played_uci = infer_played_uci(board_before, board_after)
    if not played_uci:
        return jsonify({"error": "Could not infer played_uci; pass played_uci from client"}), 400

    try:
        with _ENGINE_LOCK:
            engine = get_engine()
            eb = eval_white_cp(board_before, engine)
            ea, mate_after_pov = eval_white_cp_and_mover_mate_pov(board_after, engine, mover)
            top_uci = multipv_root_uci(board_before, engine, MULTIPV_LINES)

            best_uci = top_uci[0] if top_uci else None
            if not best_uci:
                return jsonify({"error": "Engine returned no principal variation"}), 500

            # Second MultiPV eval at root (for BRILLIANT-style heuristic) — eye-on-chess useClientAnalysis
            next_best_white = next_best_eval_white_from_multipv(
                board_before, engine, ENGINE_DEPTH
            )

            classification, cp_loss_eye, eye_dbg = classify_move_eye_on_chess(
                fen_before,
                played_uci,
                int(eb["eval_cp"]),
                int(ea["eval_cp"]),
                best_uci,
                next_best_white,
            )

            phase_before = detect_game_phase(board_before)

            polyglot_book_move = (
                phase_before == "opening" and is_book_move(board_before, played_uci)
            )

            if board_after.is_checkmate():
                classification = "checkmate"
            elif polyglot_book_move:
                classification = "book"

            # Debug: centipawn loss vs *best continuation* (child positions), not used for labels
            try:
                cp_vs_best, w_after_best, w_after_played = cp_loss_vs_best_continuation(
                    board_before, board_after, best_uci, mover, engine
                )
            except chess.IllegalMoveError:
                cp_vs_best, w_after_best, w_after_played = None, None, None

            root_delta_cp = mover_delta_cp(eb["eval_cp"], ea["eval_cp"], mover)

            phase_info = detect_game_phase_debug(board_after)

            is_checkmate_on_board = board_after.is_checkmate()

            return jsonify(
                {
                    "fen_before": fen_before,
                    "fen_after": fen_after,
                    "mover": mover,
                    "played_uci": played_uci,
                    "best_uci": best_uci,
                    "top_moves_uci": top_uci,
                    "eval_before_cp": eb["eval_cp"],
                    "eval_after_cp": ea["eval_cp"],
                    "eval_best_child_cp": w_after_best,
                    "eval_played_child_cp": w_after_played,
                    "cp_loss_eye_on_chess": round(cp_loss_eye, 2),
                    "cp_loss_vs_best": round(cp_vs_best, 2) if cp_vs_best is not None else None,
                    "next_best_eval_white": next_best_white,
                    "classifier": "eye-on-chess (amiwrpremium/eye-on-chess classify.ts)",
                    "classifier_debug": eye_dbg,
                    "delta_cp": root_delta_cp,
                    "classification": classification,
                    "phase_before_move": phase_before,
                    "is_book_move": polyglot_book_move,
                    "opening_book_path": OPENING_BOOK_PATH,
                    "book_debug": {
                        "opening_book_path": OPENING_BOOK_PATH,
                        "opening_book_path_exists": os.path.isfile(OPENING_BOOK_PATH),
                    },
                    "game_phase": phase_info["phase"],
                    "game_phase_detail": phase_info,
                    "mate_before": eb["mate"],
                    "mate_after": ea["mate"],
                    "is_checkmate_on_board": is_checkmate_on_board,
                    "is_mate_sequence": mate_after_pov["is_mate_sequence"],
                    "mate_in": mate_after_pov["mate_in"],
                    "mate_for_mover": mate_after_pov["mate_for_mover"],
                    "mate_score_pov_debug": mate_after_pov.get("mate_score_pov_repr"),
                }
            )
    except FileNotFoundError as e:
        return jsonify({"error": str(e)}), 500
    except chess.engine.EngineError as e:
        return jsonify({"error": f"Engine error: {e}"}), 500


if __name__ == "__main__":
    test_board = chess.Board()
    if not os.path.isfile(OPENING_BOOK_PATH):
        print("ERROR: Opening book missing at", OPENING_BOOK_PATH)
    print("=== START POSITION BOOK TEST ===")
    print(is_book_move(test_board, "e2e4"))
    print(is_book_move(test_board, "d2d4"))
    # use_reloader=False: Stockfish runs in a child process; the debug reloader would fork
    # and break the engine handle. Set debug=False if you prefer no interactive debugger.
    # Default 5001: macOS often reserves 5000 for AirPlay Receiver.
    port = int(os.environ.get("PORT", "5001"))
    app.run(host="127.0.0.1", port=port, debug=True, use_reloader=False)
