#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$(pwd)"
python3 -m pytest backend/tests -q
(cd frontend && npm test)
