"""Run the development server: ``python -m chess_audio``."""

import atexit

from chess_audio import config
from chess_audio.app import app
from chess_audio.engine import close_engine

atexit.register(close_engine)

if __name__ == "__main__":
    # The debug reloader forks the process, which breaks the Stockfish child process handle.
    app.run(host="127.0.0.1", port=config.PORT, debug=True, use_reloader=False)
