#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/frontend"
npm install
npm run build
rm -rf "$ROOT/desktop/ui"
mkdir -p "$ROOT/desktop/ui"
cp -a "$ROOT/frontend/dist/." "$ROOT/desktop/ui/"
cd "$ROOT/desktop"
go test ./...
mkdir -p "$ROOT/desktop/dist"
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-s -w -H windowsgui" -o "$ROOT/desktop/dist/GoldenDogRadar.exe" .
# Linux helper for local check
go build -trimpath -ldflags "-s -w" -o "$ROOT/desktop/dist/golden-dog-radar" .
echo "Windows exe: $ROOT/desktop/dist/GoldenDogRadar.exe"
ls -lh "$ROOT/desktop/dist"
