#!/usr/bin/env bash
# Restart the Adaptive Chess Audio Engine dev server (default port 5001).
# Usage: scripts/restart_server.sh
#   or:  PORT=8080 scripts/restart_server.sh
#
# If the server is running in another terminal, leave it running and run this
# from a second terminal — or press Ctrl+C there first, then run this script.

set -e
cd "$(dirname "$0")/.."
export PORT="${PORT:-5001}"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
else
  echo "No .venv found. Run: python3 -m venv .venv && pip install -r requirements.txt"
  exit 1
fi

export STOCKFISH_PATH="${STOCKFISH_PATH:-stockfish}"

echo "Stopping anything listening on TCP port $PORT (if any)..."
# macOS: plain `lsof -ti :PORT` often misses LISTEN sockets; prefer LISTEN filter.
for pid in $(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true); do
  [[ -n "$pid" ]] && kill -9 "$pid" 2>/dev/null || true
done
for pid in $(lsof -ti tcp:"$PORT" 2>/dev/null || true); do
  [[ -n "$pid" ]] && kill -9 "$pid" 2>/dev/null || true
done
for pid in $(lsof -ti ":$PORT" 2>/dev/null || true); do
  [[ -n "$pid" ]] && kill -9 "$pid" 2>/dev/null || true
done
sleep 1

echo "Starting server on http://127.0.0.1:$PORT ..."
exec python -m chess_audio
