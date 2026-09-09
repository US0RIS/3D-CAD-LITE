#!/bin/zsh
set -e
cd "$(dirname "$0")"
if command -v python3.11 >/dev/null 2>&1; then PY=python3.11; elif command -v python3.12 >/dev/null 2>&1; then PY=python3.12; else PY=python3; fi
if [ ! -d .venv ]; then
  "$PY" -m venv .venv
fi
source .venv/bin/activate
python - <<'PY' >/dev/null 2>&1 || pip install -r requirements.txt
import cadquery, fastapi, scipy, uvicorn, multipart
PY
(sleep 2; open http://127.0.0.1:8765 >/dev/null 2>&1 || true) &
python server.py
