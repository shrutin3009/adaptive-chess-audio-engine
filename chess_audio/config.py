"""Runtime settings. Every value can be overridden with an environment variable of the same name."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

STOCKFISH_PATH = os.environ.get(
    "STOCKFISH_PATH",
    "stockfish",
)
OPENING_BOOK_PATH = os.environ.get("OPENING_BOOK_PATH", str(PROJECT_ROOT / "gm2001.bin"))

# Search depth for move analysis (higher is slower and more accurate).
ENGINE_DEPTH = int(os.environ.get("ENGINE_DEPTH", "12"))
# Number of engine candidate moves compared against the played move.
MULTIPV_LINES = int(os.environ.get("MULTIPV_LINES", "10"))

PHASE_ENDGAME_MAX_MATERIAL = int(os.environ.get("PHASE_ENDGAME_MAX_MATERIAL", "13"))
PHASE_OPENING_MAX_FULLMOVE = int(os.environ.get("PHASE_OPENING_MAX_FULLMOVE", "15"))
PHASE_OPENING_MAX_MATERIAL_LOSS = float(os.environ.get("PHASE_OPENING_MAX_MATERIAL_LOSS", "6"))

# 5001 because macOS reserves 5000 for AirPlay Receiver.
PORT = int(os.environ.get("PORT", "5001"))
