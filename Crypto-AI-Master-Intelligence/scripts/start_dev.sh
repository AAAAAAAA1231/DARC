#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
if [[ ! -f .env ]]; then cp .env.example .env; fi
if [[ ! -d frontend/node_modules ]]; then
  (cd frontend && npm install && npm run build)
fi
export PYTHONPATH="$(pwd)"
python3 -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
