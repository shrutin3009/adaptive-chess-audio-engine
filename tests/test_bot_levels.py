import chess.engine
import pytest

from chess_audio.bot_levels import FULL_STRENGTH_OPTIONS, apply_bot_level, normalize_difficulty, reset_engine_strength


@pytest.mark.parametrize(
    "raw, expected",
    [("easy", "easy"), (" Hard ", "hard"), ("MEDIUM", "medium"), ("impossible", "medium"), (None, "medium"), ("", "medium")],
)
def test_normalize_difficulty(raw, expected):
    assert normalize_difficulty(raw) == expected


@pytest.mark.parametrize(
    "difficulty, options, limit",
    [
        ("easy", {"UCI_LimitStrength": False, "Skill Level": 3}, chess.engine.Limit(depth=4, time=0.12)),
        ("medium", {"UCI_LimitStrength": False, "Skill Level": 10}, chess.engine.Limit(depth=9, time=0.18)),
        (
            "hard",
            {"UCI_LimitStrength": True, "UCI_Elo": 1800, "Skill Level": 12},
            chess.engine.Limit(depth=12, time=0.22),
        ),
    ],
)
def test_apply_bot_level_presets(fake_engine, difficulty, options, limit):
    returned = apply_bot_level(fake_engine, difficulty)
    assert fake_engine.configured == [options]
    assert (returned.depth, returned.time) == (limit.depth, limit.time)


def test_elo_is_clamped_to_engine_reported_range(fake_engine):
    fake_engine.options["UCI_Elo"] = chess.engine.Option("UCI_Elo", "spin", 2000, 2000, 2500, [])
    apply_bot_level(fake_engine, "hard")
    assert fake_engine.configured[-1]["UCI_Elo"] == 2000


def test_reset_restores_full_strength(fake_engine):
    reset_engine_strength(fake_engine)
    assert fake_engine.configured == [FULL_STRENGTH_OPTIONS]
