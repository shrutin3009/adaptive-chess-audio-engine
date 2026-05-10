"""
Centralized Stockfish strength presets for human vs bot.
Levels: easy, medium, hard.
"""

from __future__ import annotations

import chess.engine

ENGINE_FULL_STRENGTH_UCI: dict[str, bool | int] = {
    "UCI_LimitStrength": False,
    "Skill Level": 20,
}

# UCI_Elo with UCI_LimitStrength: supported range depends on Stockfish build (some old builds floor ~1320).
BOT_LEVELS: dict[str, dict[str, object]] = {
    "easy": {
        "label": "Easy",
        "uci_options": {
            "UCI_LimitStrength": True,
            "UCI_Elo": 500,
            "Skill Level": 0,
        },
        "limit": chess.engine.Limit(depth=3, time=0.04),
    },
    "medium": {
        "label": "Medium",
        "uci_options": {
            "UCI_LimitStrength": True,
            "UCI_Elo": 1200,
            "Skill Level": 5,
        },
        "limit": chess.engine.Limit(depth=6, time=0.09),
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


def apply_bot_level(engine: chess.engine.SimpleEngine, difficulty: str) -> chess.engine.Limit:
    cfg = BOT_LEVELS[normalize_difficulty(difficulty)]
    uci = cfg["uci_options"]
    assert isinstance(uci, dict)
    engine.configure(uci)
    lim = cfg["limit"]
    assert isinstance(lim, chess.engine.Limit)
    return lim


def reset_engine_strength(engine: chess.engine.SimpleEngine) -> None:
    engine.configure(ENGINE_FULL_STRENGTH_UCI)
