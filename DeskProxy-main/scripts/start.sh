#!/usr/bin/env bash
# ── DeskProxy Enterprise – Startup Script ─────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Load .env if present
if [[ -f ".env" ]]; then
    set -a
    source .env
    set +a
    echo "[start.sh] Loaded .env"
fi

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"
LOG_LEVEL="${LOG_LEVEL:-info}"

echo "[start.sh] Starting DeskProxy Enterprise on ${HOST}:${PORT}"
exec uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --log-level "${LOG_LEVEL,,}"
