#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$ROOT"
cd "$ROOT/frontend"
if [ ! -d node_modules ]; then
  npm install
fi
cd "$ROOT"
python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8787 &
UVPID=$!
trap 'kill $UVPID 2>/dev/null || true' EXIT
cd "$ROOT/frontend"
npm run dev -- --host 0.0.0.0 --port 5173
