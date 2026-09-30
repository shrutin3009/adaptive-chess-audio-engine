# ChessMusic (Chess and Music)

Human **vs computer** (Stockfish) in the browser. Choose **easy**, **medium**, or **hard** bot strength (`bot_levels.py`). Choose **White** or **Black**; the board orients to your side.

After each **human** move, the server classifies it. The **primary** labels come from an **Eye on Chess**–style classifier (`eye_on_chess_classify.py`): **centipawn loss** from the mover’s perspective using the root evaluation **before** vs **after** the move (both in **White’s point of view**, adjusted so “loss” means worse for whoever moved).

**Audio (see `static/app.js`):**

- **Easy** — Web Audio **sine** stings per label; **no** Medium/Hard move WAVs; **Easy** pack **`ambience.wav`** for the bed; resign uses a short synth gesture (no pack mate-loss / resign MP3).
- **Medium / Hard** — WAVs under `static/audio/medium/` and `static/audio/hard/` in the repo (move stings, ambience, mate loss, etc.), plus shared static stings where used; mix constants differ (including Hard-only tweaks for some labels).

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

---

## Preview / test sounds (not on the game page)

Pack audio files live under **`static/audio/<pack>/`** and shared stings under **`static/audio/shared/`**; Flask serves them at the same paths. There is **no** sound tester UI on the chess page — use this section instead.

### All sounds in one page (`sound_test.html`)

The repo includes **[`static/sound_test.html`](./static/sound_test.html)**, a standalone page with **HTML5 audio controls** for every pack file plus the shared static stings. It uses the **same HTTP paths** as the game (`/static/audio/...`).

**How to use it**

1. Start the Flask app (e.g. `scripts/restart_server.sh`).
2. Open **`http://127.0.0.1:5001/static/sound_test.html`** in your browser (use your `PORT` if not `5001`).

Opening `sound_test.html` as a local `file://` document will **not** work: the audio elements expect those paths on the running server. Keep the dev server up while testing.

### On GitHub (or any clone)

Click a link to open the file in the browser; GitHub will show or download the asset (WAV/MP3).

**Easy** — move labels use **synth** in the app; only ambience is a pack WAV.

| Role | File |
|------|------|
| Ambience bed | [static/audio/easy/ambience.wav](./static/audio/easy/ambience.wav) |

**Medium**

| Role | File |
|------|------|
| Ambience bed | [static/audio/medium/ambience.wav](./static/audio/medium/ambience.wav) |
| Mate / resign lead-in | [static/audio/medium/checkmate_loss.wav](./static/audio/medium/checkmate_loss.wav) |
| **best** | [static/audio/medium/best.wav](./static/audio/medium/best.wav) |
| **great** | [static/audio/medium/great.wav](./static/audio/medium/great.wav) |
| **excellent** | [static/audio/medium/excellent.wav](./static/audio/medium/excellent.wav) |
| **good** | [static/audio/medium/good.wav](./static/audio/medium/good.wav) |
| **book** | [static/audio/medium/book.wav](./static/audio/medium/book.wav) |
| **inaccuracy** | [static/audio/medium/inaccuracy.wav](./static/audio/medium/inaccuracy.wav) |
| **mistake** | [static/audio/medium/mistake.wav](./static/audio/medium/mistake.wav) |
| **blunder** | [static/audio/medium/blunder.wav](./static/audio/medium/blunder.wav) |
| **checkmate** (win sting, pack) | [static/audio/medium/checkmate_win.wav](./static/audio/medium/checkmate_win.wav) |

**Hard** — same roles and filenames as Medium.

| Role | File |
|------|------|
| Ambience bed | [static/audio/hard/ambience.wav](./static/audio/hard/ambience.wav) |
| Mate / resign lead-in | [static/audio/hard/checkmate_loss.wav](./static/audio/hard/checkmate_loss.wav) |
| **best** | [static/audio/hard/best.wav](./static/audio/hard/best.wav) |
| **great** | [static/audio/hard/great.wav](./static/audio/hard/great.wav) |
| **excellent** | [static/audio/hard/excellent.wav](./static/audio/hard/excellent.wav) |
| **good** | [static/audio/hard/good.wav](./static/audio/hard/good.wav) |
| **book** | [static/audio/hard/book.wav](./static/audio/hard/book.wav) |
| **inaccuracy** | [static/audio/hard/inaccuracy.wav](./static/audio/hard/inaccuracy.wav) |
| **mistake** | [static/audio/hard/mistake.wav](./static/audio/hard/mistake.wav) |
| **blunder** | [static/audio/hard/blunder.wav](./static/audio/hard/blunder.wav) |
| **checkmate** (win sting, pack) | [static/audio/hard/checkmate_win.wav](./static/audio/hard/checkmate_win.wav) |

**Shared static stings** (served from `static/`)

| Role | File |
|------|------|
| Checkmate (extra layer in Medium/Hard win sequence) | [static/audio/shared/checkmate.wav](./static/audio/shared/checkmate.wav) |
| Resign sting (not Easy) | [static/audio/shared/resign.mp3](./static/audio/shared/resign.mp3) |

### With the dev server (matches in-game URLs)

1. Start the app: `scripts/restart_server.sh` (default **http://127.0.0.1:5001** — override with `PORT=…`).
2. Either open **`/static/sound_test.html`** (see above) **or** paste individual URLs in the browser — same assets as the UI.

Base URL: `http://127.0.0.1:5001`

Examples:

- `http://127.0.0.1:5001/static/audio/medium/ambience.wav`
- `http://127.0.0.1:5001/static/audio/hard/checkmate_loss.wav`
- `http://127.0.0.1:5001/static/audio/shared/checkmate.wav`

Replace `medium` / `hard` / `easy` and the filename to audition every file listed in the tables above.

To push an updated pack WAV: overwrite **`static/audio/…`** locally, then run **`git add static/audio/…`**, **`git commit`**, **`git push`** so GitHub matches your machine.
