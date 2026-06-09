#!/usr/bin/env bash
#
# One-shot launcher for the Audio Inspect web-app.
# Starts the Django REST backend and the React (Vite) front-end together.
#
# Usage:
#   ./start.sh
#
# Requirements:
#   - conda env "audio_visual_web" created from environment.yml
#       conda env create -f environment.yml
#   - front-end deps installed (the script will run `npm install` if missing)
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
CONDA_ENV="audio_visual_web"

BACKEND_PORT=8000
FRONTEND_PORT=5173

cleanup() {
  echo ""
  echo "[start.sh] Shutting down services..."
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Resolve a command runner that executes inside the conda env when available.
if command -v conda >/dev/null 2>&1; then
  RUN_IN_ENV=(conda run -n "$CONDA_ENV" --no-capture-output)
  echo "[start.sh] Using conda env: $CONDA_ENV"
else
  RUN_IN_ENV=()
  echo "[start.sh] WARNING: conda not found, using current Python/Node on PATH."
fi

echo "[start.sh] Starting Django backend on :$BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  "${RUN_IN_ENV[@]}" python manage.py runserver "0.0.0.0:$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "[start.sh] Preparing front-end ..."
(
  cd "$FRONTEND_DIR"
  if [[ ! -d node_modules ]]; then
    echo "[start.sh] Installing front-end dependencies (npm install) ..."
    "${RUN_IN_ENV[@]}" npm install
  fi
  echo "[start.sh] Starting Vite dev server on :$FRONTEND_PORT ..."
  "${RUN_IN_ENV[@]}" npm run dev -- --port "$FRONTEND_PORT" --host
) &
FRONTEND_PID=$!

echo ""
echo "[start.sh] Backend:  http://localhost:$BACKEND_PORT/api/"
echo "[start.sh] Frontend: http://localhost:$FRONTEND_PORT/"
echo "[start.sh] Press Ctrl+C to stop both."

wait
