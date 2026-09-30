"""The shared Stockfish process and helpers that turn its scores into White-POV centipawns."""

from __future__ import annotations

import os
import threading
from typing import Any, NamedTuple, Optional

import chess
import chess.engine

from chess_audio import config

MATE_SCORE_CP = 10_000

# There is a single UCI process, so every engine command must hold this lock.
engine_lock = threading.Lock()
_engine: Optional[chess.engine.SimpleEngine] = None


def get_engine() -> chess.engine.SimpleEngine:
    global _engine
    if _engine is None:
        if not os.path.isfile(config.STOCKFISH_PATH):
            raise FileNotFoundError(
                f"Stockfish not found at {config.STOCKFISH_PATH!r}. Install it "
                "(brew install stockfish, apt install stockfish, or https://stockfishchess.org/download/) "
                "or set STOCKFISH_PATH to the binary."
            )
        _engine = chess.engine.SimpleEngine.popen_uci(config.STOCKFISH_PATH)
    return _engine


def close_engine() -> None:
    global _engine
    if _engine is not None:
        _engine.quit()
        _engine = None


def white_centipawns(score: chess.engine.Score) -> int:
    """Centipawns from White's side; a forced mate becomes +/-MATE_SCORE_CP."""
    if score.is_mate():
        moves = score.mate()
        return MATE_SCORE_CP if moves and moves > 0 else -MATE_SCORE_CP
    cp = score.score()
    return int(cp) if cp is not None else 0


def _depth_limit() -> chess.engine.Limit:
    return chess.engine.Limit(depth=config.ENGINE_DEPTH)


def evaluate_white_cp(board: chess.Board, engine: chess.engine.SimpleEngine) -> dict[str, Any]:
    score = engine.analyse(board, _depth_limit())["score"].white()
    return {"eval_cp": white_centipawns(score), "mate": score.is_mate(), "mate_in": score.mate()}


def evaluate_after_move(
    board_after_move: chess.Board,
    engine: chess.engine.SimpleEngine,
    mover: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """
    One analysis of the position after a move, returning the White-POV evaluation and the
    mate distance from the mover's side (only Stockfish mate scores count as a mate sequence).
    """
    score = engine.analyse(board_after_move, _depth_limit())["score"]
    white = score.white()
    evaluation = {"eval_cp": white_centipawns(white), "mate": white.is_mate(), "mate_in": white.mate()}

    mover_score = score.pov(chess.WHITE if mover == "w" else chess.BLACK)
    mate_in = mover_score.mate()
    mate_info = {
        "is_mate_sequence": mover_score.is_mate(),
        "mate_in": mate_in,
        "mate_for_mover": mate_in is not None and mate_in > 0,
        "mate_score_pov_repr": repr(mover_score),
    }
    return evaluation, mate_info


class PrincipalLine(NamedTuple):
    uci: str  # first move of the line, "" if the engine gave none
    white_cp: int


def principal_lines(board: chess.Board, engine: chess.engine.SimpleEngine, count: int) -> list[PrincipalLine]:
    """
    The engine's best lines from one MultiPV search, best first. At least two lines are
    requested because the classifier's sacrifice heuristic needs the second-best score.
    """
    infos = engine.analyse(board, _depth_limit(), multipv=max(2, count))
    if not isinstance(infos, list):
        infos = [infos]
    return [
        PrincipalLine(info["pv"][0].uci() if info.get("pv") else "", white_centipawns(info["score"].white()))
        for info in infos
    ]
