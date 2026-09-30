"""Stockfish strength presets for the bot: easy, medium and hard."""

from __future__ import annotations

import chess.engine

# Fallback bounds used when the engine does not report its own (Stockfish 18 values).
_UCI_ELO_RANGE = (1320, 3190)
_SKILL_LEVEL_RANGE = (0, 20)

FULL_STRENGTH_OPTIONS: dict[str, bool | int] = {
    "UCI_LimitStrength": False,
    "Skill Level": 20,
}

# Easy and medium weaken the engine with Skill Level and a shallow search only, because
# UCI_Elo has a build-specific floor (1320 on Stockfish 18) and rejects lower values.
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
    key = (key or "medium").strip().lower()
    return key if key in BOT_LEVELS else "medium"


def _engine_range(engine: chess.engine.SimpleEngine, option_name: str, fallback: tuple[int, int]) -> tuple[int, int]:
    option = engine.options.get(option_name)
    if option is not None and option.min is not None and option.max is not None:
        return int(option.min), int(option.max)
    return fallback


def _clamp(value: int, bounds: tuple[int, int]) -> int:
    low, high = bounds
    return max(low, min(high, value))


def _clamp_to_engine_limits(
    preset: dict[str, bool | int], engine: chess.engine.SimpleEngine
) -> dict[str, bool | int]:
    """Fit a preset into the option ranges the running engine accepts, so configure() never fails."""
    options = dict(preset)
    if options.get("UCI_LimitStrength") and "UCI_Elo" in options:
        options["UCI_Elo"] = _clamp(int(options["UCI_Elo"]), _engine_range(engine, "UCI_Elo", _UCI_ELO_RANGE))
    else:
        options.pop("UCI_Elo", None)
    if "Skill Level" in options:
        options["Skill Level"] = _clamp(
            int(options["Skill Level"]), _engine_range(engine, "Skill Level", _SKILL_LEVEL_RANGE)
        )
    return options


def apply_bot_level(engine: chess.engine.SimpleEngine, difficulty: str) -> chess.engine.Limit:
    level = BOT_LEVELS[normalize_difficulty(difficulty)]
    preset = level["uci_options"]
    limit = level["limit"]
    assert isinstance(preset, dict) and isinstance(limit, chess.engine.Limit)
    engine.configure(_clamp_to_engine_limits(preset, engine))
    return limit


def reset_engine_strength(engine: chess.engine.SimpleEngine) -> None:
    engine.configure(FULL_STRENGTH_OPTIONS)
