#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
PYTHON="$BACKEND_DIR/.venv/bin/python"
FRONTEND_MODE="dev"
if [[ "${1:-}" == "preview" ]]; then
  FRONTEND_MODE="preview"
fi

if [[ ! -x "$PYTHON" ]]; then
  echo "[INFO] Creating the backend virtual environment..."
  python3 -m venv "$BACKEND_DIR/.venv"
fi

if ! "$PYTHON" -m pip --version >/dev/null 2>&1; then
  "$PYTHON" -m ensurepip --upgrade
fi

if ! "$PYTHON" -c "import fastapi, sqlalchemy, redis, asyncpg, pydantic_settings, jwt, pyotp, qrcode" >/dev/null 2>&1; then
  echo "[INFO] Installing backend dependencies..."
  "$PYTHON" -m pip install -r "$BACKEND_DIR/requirements-local.txt"
fi

if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
  echo "[INFO] Installing frontend dependencies..."
  npm --prefix "$FRONTEND_DIR" install
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "[INFO] Created .env from .env.example"
fi

if [[ ! -f "$ROOT_DIR/keys/jwt_private.pem" ]]; then
  (cd "$BACKEND_DIR" && "$PYTHON" scripts/generate_jwt_keys.py)
fi

echo "[INFO] Preparing the local PostgreSQL database..."
(cd "$BACKEND_DIR" && "$PYTHON" scripts/setup_database.py) || {
  echo "[ERROR] Database setup failed. Ensure local PostgreSQL is running and .env has the correct credentials."
  exit 1
}

declare -a CHILD_PIDS=()

cleanup() {
  trap - INT TERM EXIT
  if ((${#CHILD_PIDS[@]})); then
    kill "${CHILD_PIDS[@]}" 2>/dev/null || true
    wait "${CHILD_PIDS[@]}" 2>/dev/null || true
  fi
}
trap cleanup INT TERM EXIT

(cd "$BACKEND_DIR" && exec "$PYTHON" -m uvicorn main:app --reload --port 8080) &
CHILD_PIDS+=("$!")

(cd "$FRONTEND_DIR" && exec npm run "$FRONTEND_MODE") &
CHILD_PIDS+=("$!")

echo "[OK] Local applications are starting."
echo "Frontend: http://localhost:3001"
echo "API docs: http://localhost:8080/docs"
echo "Frontend mode: $FRONTEND_MODE (use ./start-local.sh preview for performance checks)"
echo "Press Ctrl+C to stop both applications."

wait
