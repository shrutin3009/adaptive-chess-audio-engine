# ChessMusic (Chess and Music)

Human **vs computer** (Stockfish) in the browser. Choose **easy**, **medium**, or **hard** bot strength (`bot_levels.py`). Choose **White** or **Black**; the board orients to your side.

After each **human** move, the server classifies it. The **primary** labels come from an **Eye on Chess**–style classifier (`eye_on_chess_classify.py`): **centipawn loss** from the mover’s perspective using the root evaluation **before** vs **after** the move (both in **White’s point of view**, adjusted so “loss” means worse for whoever moved).

**Audio (see `static/app.js`):**

- **Easy** — Web Audio **sine** stings per label; **no** Medium/Hard move WAVs; **Easy** pack **`ambience.wav`** for the bed; resign uses a short synth gesture (no pack mate-loss / resign MP3).
- **Medium / Hard** — WAVs under `sounds/Medium/` and `sounds/Hard/` (move stings, ambience, mate loss, etc.), plus shared static stings where used; mix constants differ (including Hard-only tweaks for some labels).

---

## Core labels (Eye on Chess thresholds)

Classification uses how much the position’s evaluation worsened for the player who moved, in centipawns:

| Label | Typical meaning | Approx. cp loss |
|--------|------------------|-----------------|
| **best** | Either only one legal move (**forced**), or your move matches Stockfish’s **best root move** (MultiPV line 1). | 0 or minimal |
| **great** | Very accurate play (`cp_loss` ≤ 5), or a **brilliant**-style pattern: sacrifice + engine second line much worse than staying on best. | ≤ 5 (or brilliant heuristic) |
| **excellent** | Strong move with small eval drop. | ≤ 25 |
| **good** | Solid move with moderate eval cost. | ≤ 50 |
| **inaccuracy** | Noticeable slip. | ≤ 100 |
| **mistake** | Serious error. | ≤ 200 |
| **blunder** | Severe error; eval collapses for the mover. | > 200 |

Fine points:

- **Forced move**: If there is exactly **one** legal move, the label is **best** (you had no choice).
- **Engine best**: If your played UCI equals Stockfish’s top root move, the label is **best** even if other thresholds would apply.
- **Brilliant → great**: Under tight `cp_loss`, a sacrifice heuristic can upgrade to **great** (see `classify_move_eye_on_chess`).

---

## Overrides (applied after the core classifier)

These replace the Eye on Chess label when their conditions match:

| Label | When |
|--------|------|
| **checkmate** | The move **delivers checkmate** on the board (`board_after.is_checkmate()`). Takes priority over everything below for that response. |
| **book** | **Opening phase** (see `game_phase.py`) **and** the move appears in the configured **Polyglot** opening book (`opening_book.py`). Overrides normal engine labels like **best** / **excellent**, but not **checkmate**. |

---

## Summary list of possible `classification` strings

You may see exactly one of:

`best`, `great`, `excellent`, `good`, `inaccuracy`, `mistake`, `blunder`, `book`, `checkmate`.

Mapping to playback is in **`static/app.js`** (pack paths, `MIX_*` levels, synth fallback, easy vs medium/hard).
