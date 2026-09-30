#!/usr/bin/env bash
# Restart the Adaptive Chess Audio Engine dev server (default port 5001).
# Usage: scripts/restart_server.sh
#   or:  PORT=8080 scripts/restart_server.sh
#
# Settings come from the environment, then from .env in the project root if present
# (see .env.example). Stops whatever is already listening on the port first.

set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi
export PORT="${PORT:-5001}"

if [[ -f .venv/bin/activate ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
else
  echo "No .venv found. Run: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  exit 1
fi

pids="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
if [[ -n "$pids" ]]; then
  echo "Stopping the process listening on port $PORT..."
  kill $pids 2>/dev/null || true
  for _ in 1 2 3 4 5; do
    sleep 1
    lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1 || break
  done
  remaining="$(lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null || true)"
  [[ -n "$remaining" ]] && kill -9 $remaining 2>/dev/null || true
fi

echo "Starting server on http://127.0.0.1:$PORT ..."
exec python -m chess_audio
