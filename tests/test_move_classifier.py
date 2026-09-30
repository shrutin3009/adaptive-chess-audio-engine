import chess
import pytest

from chess_audio.move_classifier import classify_move, cp_loss_from_evals, is_sacrifice

START = chess.STARTING_FEN
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


@pytest.mark.parametrize(
    "cp_loss, expected",
    [
        (0, "great"),
        (5, "great"),
        (6, "excellent"),
        (10, "excellent"),
        (25, "excellent"),
        (26, "good"),
        (50, "good"),
        (51, "inaccuracy"),
        (100, "inaccuracy"),
        (101, "mistake"),
        (200, "mistake"),
        (201, "blunder"),
    ],
)
def test_threshold_ladder_for_white(cp_loss, expected):
    label, loss, _ = classify_move(START, "e2e4", 0, -cp_loss, "d2d4", None)
    assert label == expected
    assert loss == cp_loss


def test_black_mover_loss_uses_flipped_sign():
    label, loss, _ = classify_move(AFTER_E4, "e7e5", 0, 60, "c7c5", None)
    assert (label, loss) == ("inaccuracy", 60)


def test_eval_improvement_clamps_to_zero_loss():
    assert cp_loss_from_evals(0, 300, "w") == 0.0
    assert cp_loss_from_evals(0, -300, "b") == 0.0


def test_playing_engine_best_move_is_best_even_with_large_loss():
    label, loss, _ = classify_move(START, "e2e4", 0, -300, "e2e4", None)
    assert (label, loss) == ("best", 300)


def test_best_move_match_is_case_and_whitespace_insensitive():
    label, _, _ = classify_move(START, "E2E4 ", 0, -300, " e2e4", None)
    assert label == "best"


def test_single_legal_move_is_forced_best():
    fen = "k7/8/8/8/8/8/1r6/K7 w - - 0 1"
    assert len(list(chess.Board(fen).legal_moves)) == 1
    label, loss, debug = classify_move(fen, "a1b2", 0, -500, "a1b2", None)
    assert (label, loss) == ("best", 0.0)
    assert debug["forced"] is True


QUEEN_TAKES_PAWN_FEN = "4k3/3p4/8/8/8/8/8/3QK3 w - - 0 1"


def test_brilliant_sacrifice_maps_to_great():
    label, _, debug = classify_move(QUEEN_TAKES_PAWN_FEN, "d1d7", 100, 100, "e1e2", -100)
    assert label == "great"
    assert debug["brilliant"] is True


def test_sacrifice_without_big_second_line_gap_is_not_brilliant():
    label, _, debug = classify_move(QUEEN_TAKES_PAWN_FEN, "d1d7", 100, 100, "e1e2", 0)
    assert label == "great"
    assert debug["brilliant"] is False


def test_is_sacrifice():
    assert is_sacrifice(QUEEN_TAKES_PAWN_FEN, "d1d7") is True
    assert is_sacrifice(START, "e2e4") is False
    assert is_sacrifice(START, "zz") is False
