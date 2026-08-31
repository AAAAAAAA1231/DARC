#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p dist
echo ">> tests"
go test ./...
echo ">> linux"
go build -ldflags="-s -w" -o dist/HCWRadar .
echo ">> windows exe"
GOOS=windows GOARCH=amd64 go build -ldflags="-H windowsgui -s -w" -o dist/HCWRadar.exe .
ls -lh dist
