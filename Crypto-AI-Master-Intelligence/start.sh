#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONPATH="$(pwd)"
if [[ ! -f .env ]]; then cp .env.example .env; fi
python3 -m pip install -r requirements.txt
if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm install && npm run build)
elif [[ ! -d frontend/dist ]]; then
  (cd frontend && npm run build)
fi
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
