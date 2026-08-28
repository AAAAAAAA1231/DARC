#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -e . pyinstaller numpy tzdata
python3 -m PyInstaller --noconfirm --clean packaging/OpenAdvisor.spec
echo "Binary: dist/OpenAdvisor"
