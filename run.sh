#!/bin/zsh
set -e
cd "$(dirname "$0")"
if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install -q -r requirements.txt
PORT="${GYBE_PORT:-8776}"
(( sleep 1; open "http://127.0.0.1:${PORT}" ) &)
exec python -m uvicorn app.main:app --host 127.0.0.1 --port "$PORT"
