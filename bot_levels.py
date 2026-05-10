"""
Centralized Stockfish strength presets for human vs bot.
Levels: easy, medium, hard.
"""

from __future__ import annotations

import chess.engine

# Stockfish 18+ rejects UCI_Elo outside this range when UCI_LimitStrength is on.
_UCI_ELO_MIN = 1320
_UCI_ELO_MAX = 3190
_SKILL_MIN = 0
_SKILL_MAX = 20

ENGINE_FULL_STRENGTH_UCI: dict[str, bool | int] = {
    "UCI_LimitStrength": False,
    "Skill Level": 20,
}

# Easy/medium: Skill Level + shallow search only (UCI_LimitStrength off) so any Stockfish build plays
# without Elo floor/ceiling surprises. Hard: UCI_Elo band (clamped to engine-reported min/max).
BOT_LEVELS: dict[str, dict[str, object]] = {
    "easy": {
        "label": "Easy",
        "uci_options": {
            "UCI_LimitStrength": False,
            "Skill Level": 3,
        },
        "limit": chess.engine.Limit(depth=4, time=0.12),
    },
    "medium": {
        "label": "Medium",
        "uci_options": {
            "UCI_LimitStrength": False,
            "Skill Level": 10,
        },
        "limit": chess.engine.Limit(depth=9, time=0.18),
    },
    "hard": {
        "label": "Hard",
        "uci_options": {
            "UCI_LimitStrength": True,
            "UCI_Elo": 1800,
            "Skill Level": 12,
        },
        "limit": chess.engine.Limit(depth=12, time=0.22),
    },
}


def normalize_difficulty(key: str | None) -> str:
    k = (key or "medium").strip().lower()
    if k in BOT_LEVELS:
        return k
    return "medium"


def _sanitize_limit_strength_options(
    raw: dict[str, bool | int], engine: chess.engine.SimpleEngine
) -> dict[str, bool | int]:
    """Clamp to UCI bounds reported by the running engine (varies by Stockfish version)."""
    out = dict(raw)
    elo_min, elo_max = _UCI_ELO_MIN, _UCI_ELO_MAX
    elo_opt = engine.options.get("UCI_Elo")
    if elo_opt is not None and elo_opt.min is not None and elo_opt.max is not None:
        elo_min, elo_max = int(elo_opt.min), int(elo_opt.max)
    sk_min, sk_max = _SKILL_MIN, _SKILL_MAX
    sk_opt = engine.options.get("Skill Level")
    if sk_opt is not None and sk_opt.min is not None and sk_opt.max is not None:
        sk_min, sk_max = int(sk_opt.min), int(sk_opt.max)

    if out.get("UCI_LimitStrength") and "UCI_Elo" in out:
        elo = int(out["UCI_Elo"])
        out["UCI_Elo"] = max(elo_min, min(elo_max, elo))
    elif "UCI_Elo" in out:
        del out["UCI_Elo"]
    if "Skill Level" in out:
        sk = int(out["Skill Level"])
        out["Skill Level"] = max(sk_min, min(sk_max, sk))
    return out


def apply_bot_level(engine: chess.engine.SimpleEngine, difficulty: str) -> chess.engine.Limit:
    cfg = BOT_LEVELS[normalize_difficulty(difficulty)]
    uci = cfg["uci_options"]
    assert isinstance(uci, dict)
    engine.configure(_sanitize_limit_strength_options(uci, engine))
    lim = cfg["limit"]
    assert isinstance(lim, chess.engine.Limit)
    return lim


def reset_engine_strength(engine: chess.engine.SimpleEngine) -> None:
    engine.configure(ENGINE_FULL_STRENGTH_UCI)
