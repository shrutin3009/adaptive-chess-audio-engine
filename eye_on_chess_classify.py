"""
Move classification ported from the open-source Eye on Chess project:
  packages/chess/src/analysis/classify.ts
  https://github.com/amiwrpremium/eye-on-chess

Uses engine eval *before* and *after* the move (both White POV centipawns) to
compute cpLoss, then applies the same thresholds as upstream:

  cpLoss <= 5   → GREAT
  cpLoss <= 10  → BEST   (we map to "excellent" unless UCI == engine best → "best")
  cpLoss <= 25  → EXCELLENT
  cpLoss <= 50  → GOOD
  cpLoss <= 100 → INACCURACY
  cpLoss <= 200 → MISTAKE
  else          → BLUNDER

Also ports FORCED (single legal move) and BRILLIANT (sacrifice + second-line heuristic).

Output uses your app's lowercase labels: best, great, excellent, good, inaccuracy,
mistake, blunder. BRILLIANT → "great"; FORCED → "best".
"""

from __future__ import annotations

import chess
import chess.engine
from typing import Optional

PIECE_VALUES = {"p": 100, "n": 300, "b": 300, "r": 500, "q": 900, "k": 0}


def is_sacrifice(board_fen: str, move_uci: str) -> bool:
    """Port of isSacrifice() from eye-on-chess classify.ts."""
    if len(move_uci) < 4:
        return False
    try:
        b = chess.Board(board_fen)
    except ValueError:
        return False
    from_sq = move_uci[0:2]
    to_sq = move_uci[2:4]
    prom = move_uci[4:5] if len(move_uci) > 4 else None

    try:
        from_chess_sq = chess.parse_square(from_sq)
        to_chess_sq = chess.parse_square(to_sq)
    except ValueError:
        return False

    moving = b.piece_at(from_chess_sq)
    target = b.piece_at(to_chess_sq)
    if moving is None:
        return False

    av = PIECE_VALUES.get(moving.symbol().lower(), 0)
    if target is not None:
        cv = PIECE_VALUES.get(target.symbol().lower(), 0)
        if av > cv + 50:
            return True

    try:
        m = chess.Move.from_uci(move_uci if prom else move_uci[:4])
        if m not in b.legal_moves:
            if prom:
                m = chess.Move.from_uci(move_uci)
            else:
                return False
        b.push(m)
    except (ValueError, chess.IllegalMoveError):
        return False

    for mv in b.generate_legal_moves():
        if mv.to_square == to_chess_sq and target is None:
            return True
    return False


def cp_loss_from_evals(eval_before_white: int, eval_after_white: int, mover: str) -> float:
    """Same sign logic as eye-on-chess classify.ts lines 83–89."""
    if mover == "b":
        loss = float(eval_after_white - eval_before_white)
    else:
        loss = float(eval_before_white - eval_after_white)
    return max(0.0, loss)


def white_cp_from_score(pov) -> int | None:
    """python-chess Score from side-to-move root; normalize to approx centipawns White POV."""
    if pov.is_mate():
        m = pov.mate()
        return 10000 if m and m > 0 else -10000
    s = pov.score()
    return int(s) if s is not None else 0


def next_best_eval_white_from_multipv(
    board: chess.Board, engine: chess.engine.SimpleEngine, depth: int
) -> Optional[int]:
    """Second MultiPV line score in White-POV cp, matching useClientAnalysis multiPV[1].score."""
    infos = engine.analyse(
        board, chess.engine.Limit(depth=depth), multipv=2
    )
    if not isinstance(infos, list) or len(infos) < 2:
        return None
    w = infos[1]["score"].white()
    return white_cp_from_score(w)


def classify_move_eye_on_chess(
    fen_before: str,
    played_uci: str,
    eval_before_white: int,
    eval_after_white: int,
    best_move_uci: str,
    next_best_eval_white: Optional[int],
) -> tuple[str, float, dict]:
    """
    Returns (lowercase_label, cp_loss, debug_dict).

    `next_best_eval_white` should be the second MultiPV line's eval in the same units
    as eval_before_white (White POV centipawns), or None.
    """
    board = chess.Board(fen_before)
    mover = fen_before.split()[1]
    if mover not in ("w", "b"):
        mover = "w"

    dbg: dict = {"source": "eye-on-chess", "forced": False, "brilliant": False}

    if len(list(board.legal_moves)) == 1:
        dbg["forced"] = True
        return "best", 0.0, dbg

    cp_loss = cp_loss_from_evals(eval_before_white, eval_after_white, mover)

    # BRILLIANT: sacrifice + second line much worse than playing best (TS lines 91–106)
    if (
        cp_loss < 5
        and next_best_eval_white is not None
        and is_sacrifice(fen_before, played_uci)
    ):
        if mover == "b":
            next_best_loss = float(next_best_eval_white - eval_before_white)
        else:
            next_best_loss = float(eval_before_white - next_best_eval_white)
        if next_best_loss > 150:
            dbg["brilliant"] = True
            return "great", cp_loss, dbg

    best_n = best_move_uci.strip().lower()
    played_n = played_uci.strip().lower()
    if best_n and played_n == best_n:
        return "best", cp_loss, dbg

    # Threshold ladder (classify.ts lines 109–116), names mapped for this app
    if cp_loss <= 5:
        return "great", cp_loss, dbg
    if cp_loss <= 10:
        return "excellent", cp_loss, dbg
    if cp_loss <= 25:
        return "excellent", cp_loss, dbg
    if cp_loss <= 50:
        return "good", cp_loss, dbg
    if cp_loss <= 100:
        return "inaccuracy", cp_loss, dbg
    if cp_loss <= 200:
        return "mistake", cp_loss, dbg
    return "blunder", cp_loss, dbg
