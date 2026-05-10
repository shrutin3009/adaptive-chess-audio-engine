"""
Game phase detection modeled after the documented rules in **ailed-chess** (README):

  - **Endgame** if total non-pawn / non-king material on the board is <= 13 points.
    (Endgame takes priority over the others.)
  - **Opening** if fullmove <= 15 AND non-pawn / non-king material loss from start < 6 points.
  - **Middlegame** otherwise.

Piece values (pawns & kings excluded from sums): Q=9, R=5, B=3, N=3.
Baseline total at standard start = 62 (both sides).

Tweak via env: PHASE_ENDGAME_MAX_MATERIAL, PHASE_OPENING_MAX_FULLMOVE,
PHASE_OPENING_MAX_MATERIAL_LOSS.
"""

from __future__ import annotations

import os

import chess

# Standard piece values for Q/R/B/N only (same scale as ailed-chess-style descriptions)
_MAT_VAL = {
    chess.QUEEN: 9,
    chess.ROOK: 5,
    chess.BISHOP: 3,
    chess.KNIGHT: 3,
}

_ENDGAME_MAX = int(os.environ.get("PHASE_ENDGAME_MAX_MATERIAL", "13"))
_OPENING_MAX_FULLMOVE = int(os.environ.get("PHASE_OPENING_MAX_FULLMOVE", "15"))
_OPENING_MAX_LOSS = float(os.environ.get("PHASE_OPENING_MAX_MATERIAL_LOSS", "6"))


def _value_for_piece(p: chess.Piece) -> int:
    if p.piece_type in _MAT_VAL:
        return _MAT_VAL[p.piece_type]
    return 0


def total_non_pawn_non_king_material(board: chess.Board) -> int:
    """Sum of Q/R/B/N values currently on the board (both colors). Pawns and kings count 0."""
    s = 0
    for sq in chess.SQUARES:
        p = board.piece_at(sq)
        if p is None or p.piece_type in (chess.PAWN, chess.KING):
            continue
        s += _value_for_piece(p)
    return s


def _baseline_start_material() -> int:
    """Total Q/R/B/N value in the standard starting position (62)."""
    return total_non_pawn_non_king_material(chess.Board())


_BASELINE = _baseline_start_material()


def non_pawn_non_king_material_loss_from_start(board: chess.Board) -> float:
    """
    Material no longer on the board compared to the standard start, in the same units
    as total_non_pawn_non_king_material (roughly: traded heavy pieces).

    If promotions add extra queens, current total can exceed the baseline; then this
    returns 0.0 so the opening rule does not misfire on inflated totals.
    """
    cur = total_non_pawn_non_king_material(board)
    return float(max(0, _BASELINE - cur))


def detect_game_phase(board: chess.Board) -> str:
    """
    Return exactly one of: \"opening\", \"middlegame\", \"endgame\".

    Order: endgame first (priority), then opening, else middlegame.
    """
    total = total_non_pawn_non_king_material(board)
    if total <= _ENDGAME_MAX:
        return "endgame"

    loss = non_pawn_non_king_material_loss_from_start(board)
    if board.fullmove_number <= _OPENING_MAX_FULLMOVE and loss < _OPENING_MAX_LOSS:
        return "opening"

    return "middlegame"


def detect_game_phase_debug(board: chess.Board) -> dict:
    """Same as detect_game_phase plus numeric fields for APIs / logs."""
    total = total_non_pawn_non_king_material(board)
    loss = non_pawn_non_king_material_loss_from_start(board)
    phase = detect_game_phase(board)
    return {
        "phase": phase,
        "total_non_pawn_non_king_material": total,
        "non_pawn_non_king_material_loss_from_start": loss,
        "fullmove_number": board.fullmove_number,
        "thresholds": {
            "endgame_max_total": _ENDGAME_MAX,
            "opening_max_fullmove": _OPENING_MAX_FULLMOVE,
            "opening_max_material_loss": _OPENING_MAX_LOSS,
            "baseline_start_material": _BASELINE,
        },
    }
