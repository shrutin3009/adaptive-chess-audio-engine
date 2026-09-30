"""Run the development server: ``python -m chess_audio``."""

import atexit
import os

import chess

from chess_audio import config
from chess_audio.app import app
from chess_audio.engine import close_engine
from chess_audio.opening_book import is_book_move

atexit.register(close_engine)

if __name__ == "__main__":
    test_board = chess.Board()
    if not os.path.isfile(config.OPENING_BOOK_PATH):
        print("ERROR: Opening book missing at", config.OPENING_BOOK_PATH)
    print("=== START POSITION BOOK TEST ===")
    print(is_book_move(test_board, "e2e4"))
    print(is_book_move(test_board, "d2d4"))
    # The debug reloader forks the process, which breaks the Stockfish child process handle.
    app.run(host="127.0.0.1", port=config.PORT, debug=True, use_reloader=False)
