"""Polyglot opening book lookup (python-chess)."""

from __future__ import annotations

import logging
import os

import chess
import chess.polyglot

from chess_audio import config

log = logging.getLogger(__name__)


def is_book_move(board_before_move: chess.Board, played_move_uci: str) -> bool:
    if not os.path.exists(config.OPENING_BOOK_PATH):
        log.warning("Opening book file not found: %s", config.OPENING_BOOK_PATH)
        return False

    played_move = chess.Move.from_uci(played_move_uci)
    try:
        with chess.polyglot.open_reader(config.OPENING_BOOK_PATH) as reader:
            return any(entry.move == played_move for entry in reader.find_all(board_before_move))
    except Exception:
        log.exception("Could not read opening book %s", config.OPENING_BOOK_PATH)
        return False
