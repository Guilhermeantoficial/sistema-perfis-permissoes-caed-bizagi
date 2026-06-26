#!/usr/bin/env bash
set -euo pipefail
source .venv/bin/activate
python -m app.worker &
WORKER_PID=$!
trap 'kill $WORKER_PID 2>/dev/null || true' EXIT INT TERM
exec python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
