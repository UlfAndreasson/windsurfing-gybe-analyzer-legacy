#!/bin/zsh
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
PORT="${GYBE_PORT:-8776}"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT" --reload
