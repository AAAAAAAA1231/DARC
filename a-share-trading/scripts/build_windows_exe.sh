#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m nsist pynsist.cfg
mkdir -p dist
cp -f "build/nsis/大A量化研判系统.exe" dist/
echo "Windows exe: dist/大A量化研判系统.exe"
file dist/*.exe
