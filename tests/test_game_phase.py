import chess

from chess_audio.game_phase import detect_game_phase, game_phase_details, non_pawn_material


def test_start_position_is_opening_with_full_material():
    board = chess.Board()
    assert detect_game_phase(board) == "opening"
    assert non_pawn_material(board) == 62


def test_full_material_after_move_15_is_middlegame():
    board = chess.Board("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 16")
    assert detect_game_phase(board) == "middlegame"


def test_early_heavy_trades_leave_opening():
    board = chess.Board("1nbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/R1BQKBNR w KQk - 0 5")
    assert detect_game_phase(board) == "middlegame"


def test_endgame_boundary_at_13_points():
    at_limit = chess.Board("4k3/8/8/8/8/8/8/R2BK2R w - - 0 40")
    over_limit = chess.Board("4k3/8/8/8/8/8/8/RN1BK2R w - - 0 40")
    assert detect_game_phase(at_limit) == "endgame"
    assert detect_game_phase(over_limit) == "middlegame"


def test_debug_payload_shape():
    info = game_phase_details(chess.Board())
    assert info["phase"] == "opening"
    assert set(info) == {
        "phase",
        "total_non_pawn_non_king_material",
        "non_pawn_non_king_material_loss_from_start",
        "fullmove_number",
        "thresholds",
    }
    assert info["thresholds"]["baseline_start_material"] == 62
