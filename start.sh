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

# Ports in 9xxx range — avoids common 8000/8001/5173 conflicts with other local apps.
BACKEND_PORT=9081
FRONTEND_PORT=9173

# Stop any stale listener on our dedicated ports (e.g. previous ./start.sh or test run).
free_port() {
  local port=$1
  local pids
  pids=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [[ -n "$pids" ]]; then
    echo "[start.sh] Port $port busy (PID $pids) — stopping stale process..."
    # shellcheck disable=SC2086
    kill $pids 2>/dev/null || true
    sleep 1
    pids=$(lsof -t -iTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      echo "[start.sh] ERROR: port $port still in use. Stop the other app or change BACKEND_PORT/FRONTEND_PORT in start.sh."
      exit 1
    fi
  fi
}

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

free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

echo "[start.sh] Starting Django backend on :$BACKEND_PORT ..."
(
  cd "$BACKEND_DIR"
  "${RUN_IN_ENV[@]}" python manage.py runserver "127.0.0.1:$BACKEND_PORT"
) &
BACKEND_PID=$!

# Wait until our Django API is actually reachable (avoids proxy 404 from wrong server).
BACKEND_READY=0
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/api/metrics" >/dev/null 2>&1; then
    echo "[start.sh] Backend API ready on :$BACKEND_PORT"
    BACKEND_READY=1
    break
  fi
  if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
    echo "[start.sh] ERROR: Django backend exited before becoming ready."
    exit 1
  fi
  sleep 0.5
done
if [[ "$BACKEND_READY" -ne 1 ]]; then
  echo "[start.sh] ERROR: Backend did not respond on :$BACKEND_PORT within 15s."
  exit 1
fi

echo "[start.sh] Preparing front-end ..."
(
  cd "$FRONTEND_DIR"
  export AUDIO_INSPECT_BACKEND_PORT="$BACKEND_PORT"
  export AUDIO_INSPECT_FRONTEND_PORT="$FRONTEND_PORT"
  if [[ ! -d node_modules ]]; then
    echo "[start.sh] Installing front-end dependencies (npm install) ..."
    "${RUN_IN_ENV[@]}" npm install
  fi
  echo "[start.sh] Starting Vite dev server on :$FRONTEND_PORT (API -> :$BACKEND_PORT) ..."
  "${RUN_IN_ENV[@]}" npm run dev -- --port "$FRONTEND_PORT" --host
) &
FRONTEND_PID=$!

echo ""
echo "[start.sh] Backend:  http://localhost:$BACKEND_PORT/api/"
echo "[start.sh] Frontend: http://localhost:$FRONTEND_PORT/"
echo "[start.sh] Press Ctrl+C to stop both."

wait
