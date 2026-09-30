import chess
import chess.engine
import pytest

from chess_audio import config
from chess_audio import engine as engine_module
from chess_audio.bot_levels import FULL_STRENGTH_OPTIONS

START = chess.STARTING_FEN
AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"
# 1.f3 e5 2.g4 — Black to move, Qh4# available.
BEFORE_FOOLS_MATE = "rnbqkbnr/pppp1ppp/8/4p3/6P1/5P2/PPPPP2P/RNBQKBNR b KQkq - 0 2"
AFTER_FOOLS_MATE = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"

ANALYZE_MOVE_KEYS = {
    "fen_before",
    "fen_after",
    "mover",
    "played_uci",
    "best_uci",
    "top_moves_uci",
    "eval_before_cp",
    "eval_after_cp",
    "eval_best_child_cp",
    "eval_played_child_cp",
    "cp_loss_eye_on_chess",
    "cp_loss_vs_best",
    "next_best_eval_white",
    "classifier",
    "classifier_debug",
    "delta_cp",
    "classification",
    "phase_before_move",
    "is_book_move",
    "opening_book_path",
    "book_debug",
    "game_phase",
    "game_phase_detail",
    "mate_before",
    "mate_after",
    "is_checkmate_on_board",
    "is_mate_sequence",
    "mate_in",
    "mate_for_mover",
    "mate_score_pov_debug",
}


def raise_engine_error():
    raise chess.engine.EngineError("boom")


def raise_missing_binary():
    raise FileNotFoundError("Stockfish not found")


def test_index_renders(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Adaptive Chess Audio Engine" in response.data


def test_pack_sound_is_served(client):
    response = client.get("/static/audio/medium/best.wav")
    assert response.status_code == 200
    assert response.data[:4] == b"RIFF"


# /api/evaluate


@pytest.mark.parametrize("body", [{}, {"fen": 5}, {"fen": ""}])
def test_evaluate_rejects_missing_fen(client, fake_engine, body):
    assert client.post("/api/evaluate", json=body).status_code == 400


def test_evaluate_rejects_invalid_fen(client, fake_engine):
    response = client.post("/api/evaluate", json={"fen": "not a fen"})
    assert response.status_code == 400
    assert "Invalid FEN" in response.get_json()["error"]


def test_evaluate_returns_white_pov_eval(client, fake_engine):
    response = client.post("/api/evaluate", json={"fen": START})
    assert response.status_code == 200
    assert response.get_json() == {"fen": START, "eval_cp": 0, "mate": False, "mate_in": None}


def test_evaluate_reports_missing_engine_as_json_500(client, monkeypatch):
    monkeypatch.setattr(engine_module, "get_engine", raise_missing_binary)
    response = client.post("/api/evaluate", json={"fen": START})
    assert response.status_code == 500
    assert "Stockfish not found" in response.get_json()["error"]


# /api/bot-move


def test_bot_move_returns_legal_move_and_resets_strength(client, fake_engine):
    response = client.post("/api/bot-move", json={"fen": AFTER_E4, "difficulty": "hard"})
    assert response.status_code == 200
    data = response.get_json()
    assert set(data) == {"uci", "difficulty", "bot_level"}
    assert data["difficulty"] == "hard"
    assert data["bot_level"] == "Hard"
    assert chess.Move.from_uci(data["uci"]) in chess.Board(AFTER_E4).legal_moves
    assert fake_engine.configured[-1] == FULL_STRENGTH_OPTIONS


def test_bot_move_unknown_difficulty_falls_back_to_medium(client, fake_engine):
    data = client.post("/api/bot-move", json={"fen": AFTER_E4, "difficulty": "godlike"}).get_json()
    assert data["difficulty"] == "medium"


def test_bot_move_rejects_finished_game(client, fake_engine):
    response = client.post("/api/bot-move", json={"fen": AFTER_FOOLS_MATE})
    assert response.status_code == 400


def test_bot_move_rejects_missing_fen(client, fake_engine):
    assert client.post("/api/bot-move", json={}).status_code == 400


def test_bot_move_reports_engine_error_as_json_500(client, fake_engine, monkeypatch):
    monkeypatch.setattr(fake_engine, "play", lambda board, limit: raise_engine_error())
    response = client.post("/api/bot-move", json={"fen": AFTER_E4})
    assert response.status_code == 500
    assert response.get_json()["error"].startswith("Engine error")


# /api/analyze-move


def test_analyze_move_response_fields(client, fake_engine):
    response = client.post(
        "/api/analyze-move",
        json={"fen_before": START, "fen_after": AFTER_E4, "played_uci": "e2e4"},
    )
    assert response.status_code == 200
    data = response.get_json()
    assert set(data) == ANALYZE_MOVE_KEYS
    assert data["mover"] == "w"
    assert data["played_uci"] == "e2e4"
    assert data["classification"] == "book"
    assert data["is_book_move"] is True
    assert data["phase_before_move"] == "opening"
    assert len(data["top_moves_uci"]) == config.MULTIPV_LINES


def test_analyze_move_infers_played_uci(client, fake_engine):
    data = client.post("/api/analyze-move", json={"fen_before": START, "fen_after": AFTER_E4}).get_json()
    assert data["played_uci"] == "e2e4"


def test_analyze_move_second_line_eval(client, fake_engine):
    after_d4 = "rnbqkbnr/pppppppp/8/8/3P4/8/PPP1PPPP/RNBQKBNR b KQkq - 0 1"
    after_c4 = "rnbqkbnr/pppppppp/8/8/2P5/8/PP1PPPPP/RNBQKBNR b KQkq - 0 1"
    fake_engine.scores = {after_d4: 50, after_c4: 30}
    data = client.post(
        "/api/analyze-move",
        json={"fen_before": START, "fen_after": after_d4, "played_uci": "d2d4"},
    ).get_json()
    assert data["best_uci"] == "d2d4"
    assert data["top_moves_uci"][:2] == ["d2d4", "c2c4"]
    assert data["next_best_eval_white"] == 30


def test_analyze_move_checkmate_overrides_label(client, fake_engine):
    data = client.post(
        "/api/analyze-move",
        json={"fen_before": BEFORE_FOOLS_MATE, "fen_after": AFTER_FOOLS_MATE, "played_uci": "d8h4"},
    ).get_json()
    assert data["classification"] == "checkmate"
    assert data["is_checkmate_on_board"] is True
    assert data["mover"] == "b"


@pytest.mark.parametrize(
    "body",
    [{}, {"fen_before": START}, {"fen_before": START, "fen_after": "garbage"}],
)
def test_analyze_move_rejects_bad_input(client, fake_engine, body):
    assert client.post("/api/analyze-move", json=body).status_code == 400


def test_analyze_move_rejects_unrelated_positions(client, fake_engine):
    response = client.post("/api/analyze-move", json={"fen_before": START, "fen_after": AFTER_FOOLS_MATE})
    assert response.status_code == 400


def test_analyze_move_reports_engine_error_as_json_500(client, fake_engine, monkeypatch):
    monkeypatch.setattr(fake_engine, "analyse", lambda *a, **k: raise_engine_error())
    response = client.post(
        "/api/analyze-move",
        json={"fen_before": START, "fen_after": AFTER_E4, "played_uci": "e2e4"},
    )
    assert response.status_code == 500
    assert response.get_json()["error"].startswith("Engine error")
