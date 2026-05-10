#!/usr/bin/env python3
"""Write short placeholder WAV tones into static/sounds/ (stdlib only)."""

from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "static" / "sounds"

# Labels match frontend SOUND_PROFILE (Hz, duration s)
TONES = [
    ("blunder.wav", 196, 0.32),
    ("mistake.wav", 220, 0.26),
    ("inaccuracy.wav", 247, 0.22),
    ("good.wav", 294, 0.18),
    ("excellent.wav", 349, 0.2),
    ("best.wav", 392, 0.22),
    ("great.wav", 523, 0.28),
]


def write_tone(path: Path, freq: float, duration: float, volume: float = 0.25) -> None:
    framerate = 44100
    nframes = int(duration * framerate)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        for i in range(nframes):
            t = i / framerate
            sample = volume * math.sin(2 * math.pi * freq * t)
            env = min(1.0, i / 800) * min(1.0, (nframes - i) / 800)
            val = int(max(-1.0, min(1.0, sample * env)) * 32767)
            w.writeframes(struct.pack("<h", val))


def main() -> None:
    for name, freq, dur in TONES:
        write_tone(OUT / name, freq, dur)
        print("Wrote", OUT / name)


if __name__ == "__main__":
    main()
