"""End-to-end checks against a real Stockfish binary. Skipped when none is installed or configured."""

import os

import chess
import pytest

from chess_audio import config

pytestmark = pytest.mark.skipif(
    not os.path.isfile(config.STOCKFISH_PATH),
    reason="install Stockfish or set STOCKFISH_PATH to run",
)

AFTER_E4 = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1"


@pytest.mark.parametrize("difficulty", ["easy", "medium", "hard"])
def test_bot_plays_at_every_difficulty(client, difficulty):
    response = client.post("/api/bot-move", json={"fen": AFTER_E4, "difficulty": difficulty})
    assert response.status_code == 200, response.get_json()
    assert chess.Move.from_uci(response.get_json()["uci"]) in chess.Board(AFTER_E4).legal_moves


def test_analyze_move_classifies_book_opening(client):
    response = client.post(
        "/api/analyze-move",
        json={"fen_before": chess.STARTING_FEN, "fen_after": AFTER_E4, "played_uci": "e2e4"},
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["classification"] == "book"
