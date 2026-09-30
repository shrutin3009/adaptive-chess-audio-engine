"""
Game phase detection modeled after the documented rules in **ailed-chess** (README):

  - **Endgame** if total non-pawn / non-king material on the board is <= 13 points.
    (Endgame takes priority over the others.)
  - **Opening** if fullmove <= 15 AND non-pawn / non-king material loss from start < 6 points.
  - **Middlegame** otherwise.

Piece values (pawns & kings excluded from sums): Q=9, R=5, B=3, N=3.
Baseline total at standard start = 62 (both sides).

Thresholds are configurable in chess_audio.config.
"""

from __future__ import annotations

import chess

from chess_audio import config

_PIECE_POINTS = {
    chess.QUEEN: 9,
    chess.ROOK: 5,
    chess.BISHOP: 3,
    chess.KNIGHT: 3,
}


def non_pawn_material(board: chess.Board) -> int:
    """Sum of Q/R/B/N values currently on the board (both colors). Pawns and kings count 0."""
    return sum(_PIECE_POINTS.get(piece.piece_type, 0) for piece in board.piece_map().values())


_START_MATERIAL = non_pawn_material(chess.Board())


def non_pawn_material_lost(board: chess.Board) -> float:
    """
    Q/R/B/N material missing compared with the standard start position.

    Promotions can push the current total above the start total; that counts as 0 lost so the
    opening rule does not misfire.
    """
    return float(max(0, _START_MATERIAL - non_pawn_material(board)))


def detect_game_phase(board: chess.Board) -> str:
    """
    Return exactly one of: \"opening\", \"middlegame\", \"endgame\".

    Order: endgame first (priority), then opening, else middlegame.
    """
    if non_pawn_material(board) <= config.PHASE_ENDGAME_MAX_MATERIAL:
        return "endgame"

    if (
        board.fullmove_number <= config.PHASE_OPENING_MAX_FULLMOVE
        and non_pawn_material_lost(board) < config.PHASE_OPENING_MAX_MATERIAL_LOSS
    ):
        return "opening"

    return "middlegame"


def game_phase_details(board: chess.Board) -> dict:
    """detect_game_phase plus the numbers behind it (returned by the analyze-move API)."""
    return {
        "phase": detect_game_phase(board),
        "total_non_pawn_non_king_material": non_pawn_material(board),
        "non_pawn_non_king_material_loss_from_start": non_pawn_material_lost(board),
        "fullmove_number": board.fullmove_number,
        "thresholds": {
            "endgame_max_total": config.PHASE_ENDGAME_MAX_MATERIAL,
            "opening_max_fullmove": config.PHASE_OPENING_MAX_FULLMOVE,
            "opening_max_material_loss": config.PHASE_OPENING_MAX_MATERIAL_LOSS,
            "baseline_start_material": _START_MATERIAL,
        },
    }
