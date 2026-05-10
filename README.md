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

---

## Preview / test sounds (not on the game page)

Sound files live under `sounds/` and `static/sounds/`. There is **no** sound tester UI on the chess page — use this section instead.

### All sounds in one page (`sound_test.html`)

The repo includes **[`static/sound_test.html`](./static/sound_test.html)**, a standalone page with **HTML5 audio controls** for every pack file plus the shared static stings. It uses the **same URL paths** as the game (`/sounds/...` and `/static/sounds/...`).

**How to use it**

1. Start the Flask app (e.g. `./restart_server.sh`).
2. Open **`http://127.0.0.1:5001/static/sound_test.html`** in your browser (use your `PORT` if not `5001`).

Opening `sound_test.html` as a local `file://` document will **not** work: the audio elements expect those paths on the running server. Keep the dev server up while testing.

### On GitHub (or any clone)

Click a link to open the file in the browser; GitHub will show or download the asset (WAV/MP3).

**Easy** — move labels use **synth** in the app; only ambience is a pack WAV.

| Role | File |
|------|------|
| Ambience bed | [sounds/Easy/ambience.wav](./sounds/Easy/ambience.wav) |

**Medium**

| Role | File |
|------|------|
| Ambience bed | [sounds/Medium/ambience.wav](./sounds/Medium/ambience.wav) |
| Mate / resign lead-in | [sounds/Medium/checkmateLoss.wav](./sounds/Medium/checkmateLoss.wav) |
| **best** | [sounds/Medium/best.wav](./sounds/Medium/best.wav) |
| **great** | [sounds/Medium/great.wav](./sounds/Medium/great.wav) |
| **excellent** | [sounds/Medium/excellent.wav](./sounds/Medium/excellent.wav) |
| **good** | [sounds/Medium/good.wav](./sounds/Medium/good.wav) |
| **book** | [sounds/Medium/bookMove.wav](./sounds/Medium/bookMove.wav) |
| **inaccuracy** | [sounds/Medium/inaccuracy.wav](./sounds/Medium/inaccuracy.wav) |
| **mistake** | [sounds/Medium/mistake.wav](./sounds/Medium/mistake.wav) |
| **blunder** | [sounds/Medium/blunder.wav](./sounds/Medium/blunder.wav) |
| **checkmate** (win sting, pack) | [sounds/Medium/checkmate_win.wav](./sounds/Medium/checkmate_win.wav) |

**Hard** — same roles as Medium except **book** uses `book.wav`; mate loss uses a different filename.

| Role | File |
|------|------|
| Ambience bed | [sounds/Hard/ambience.wav](./sounds/Hard/ambience.wav) |
| Mate / resign lead-in | [sounds/Hard/checkmate_loss.wav](./sounds/Hard/checkmate_loss.wav) |
| **best** | [sounds/Hard/best.wav](./sounds/Hard/best.wav) |
| **great** | [sounds/Hard/great.wav](./sounds/Hard/great.wav) |
| **excellent** | [sounds/Hard/excellent.wav](./sounds/Hard/excellent.wav) |
| **good** | [sounds/Hard/good.wav](./sounds/Hard/good.wav) |
| **book** | [sounds/Hard/book.wav](./sounds/Hard/book.wav) |
| **inaccuracy** | [sounds/Hard/inaccuracy.wav](./sounds/Hard/inaccuracy.wav) |
| **mistake** | [sounds/Hard/mistake.wav](./sounds/Hard/mistake.wav) |
| **blunder** | [sounds/Hard/blunder.wav](./sounds/Hard/blunder.wav) |
| **checkmate** (win sting, pack) | [sounds/Hard/checkmate_win.wav](./sounds/Hard/checkmate_win.wav) |

**Shared static stings** (served from `static/`)

| Role | File |
|------|------|
| Checkmate (extra layer in Medium/Hard win sequence) | [static/sounds/checkmate.wav](./static/sounds/checkmate.wav) |
| Resign sting (not Easy) | [static/sounds/resign.mp3](./static/sounds/resign.mp3) |

### With the dev server (matches in-game URLs)

1. Start the app: `./restart_server.sh` (default **http://127.0.0.1:5001** — override with `PORT=…`).
2. Either open **`/static/sound_test.html`** (see above) **or** paste individual URLs in the browser — same assets as the UI.

Base URL: `http://127.0.0.1:5001`

Examples:

- `http://127.0.0.1:5001/sounds/Medium/ambience.wav`
- `http://127.0.0.1:5001/sounds/Hard/checkmate_loss.wav`
- `http://127.0.0.1:5001/static/sounds/checkmate.wav`

Replace `Medium` / `Hard` / `Easy` and the filename to audition every file listed in the tables above.
