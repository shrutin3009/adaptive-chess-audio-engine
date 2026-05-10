"""
Polyglot opening book (python-chess). Book file is fixed to the project copy of gm2001.bin.
"""

from __future__ import annotations

OPENING_BOOK_PATH = "gm2001.bin"


def is_book_move(board_before_move, played_move_uci):
    import os
    import chess
    import chess.polyglot

    if not os.path.exists(OPENING_BOOK_PATH):
        print("Opening book file not found:", OPENING_BOOK_PATH)
        return False

    played_move = chess.Move.from_uci(played_move_uci)

    try:
        with chess.polyglot.open_reader(OPENING_BOOK_PATH) as reader:
            entries = list(reader.find_all(board_before_move))
            book_moves = [entry.move for entry in entries]

            # Debug output
            print("=== BOOK DEBUG ===")
            print("FEN:", board_before_move.fen())
            print("Book moves:", [m.uci() for m in book_moves])
            print("Played move:", played_move_uci)

            return played_move in book_moves
    except Exception as e:
        print("Polyglot error:", e)
        return False
