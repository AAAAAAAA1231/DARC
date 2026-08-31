#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PATH="$PATH:$(go env GOPATH)/bin"
cd "$ROOT/frontend"
npm install
npm run build
rm -rf "$ROOT/desktop/ui"
mkdir -p "$ROOT/desktop/ui"
cp -a "$ROOT/frontend/dist/." "$ROOT/desktop/ui/"
cd "$ROOT/desktop"
go test ./...
if ! command -v go-winres >/dev/null 2>&1; then
  go install github.com/tc-hib/go-winres@latest
fi
go-winres make --in winres/winres.json --out rsrc
mkdir -p "$ROOT/desktop/dist" "$ROOT/release"
# Keep symbols (no -s -w): stripped Go binaries are commonly false-flagged.
GOOS=windows GOARCH=amd64 CGO_ENABLED=0 go build -trimpath -ldflags "-H windowsgui" -o "$ROOT/desktop/dist/GoldenDogRadar.exe" .
cp -f "$ROOT/desktop/dist/GoldenDogRadar.exe" "$ROOT/release/GoldenDogRadar.exe"
cp -f "$ROOT/desktop/dist/GoldenDogRadar.exe" "$ROOT/release/金狗雷达.exe"
cat > "$ROOT/release/若拦截请先看.txt" <<'TXT'
金狗雷达是开源研究工具，没有代码签名证书，Windows 可能提示未知发布者或误报。

第一次打开请这样：
1. 右键 GoldenDogRadar.exe（或 金狗雷达.exe）
2. 属性 → 底部勾选「解除锁定」→ 确定
3. 再双击

仍被 SmartScreen 拦住：更多信息 → 仍要运行。
不要关闭整个 Windows 安全中心。
TXT
(
  cd "$ROOT/release"
  python3 - <<'PY'
import hashlib, pathlib
p = pathlib.Path("GoldenDogRadar.exe")
print("SHA256", hashlib.sha256(p.read_bytes()).hexdigest(), p.name, p.stat().st_size)
PY
  rm -f 金狗雷达-Windows.zip
  python3 - <<'PY'
import zipfile
with zipfile.ZipFile("金狗雷达-Windows.zip","w",zipfile.ZIP_DEFLATED) as z:
    z.write("GoldenDogRadar.exe")
    z.write("金狗雷达.exe")
    z.write("若拦截请先看.txt")
print("zip ok")
PY
)
go build -trimpath -o "$ROOT/desktop/dist/golden-dog-radar" .
echo "Windows exe: $ROOT/release/GoldenDogRadar.exe"
ls -lh "$ROOT/release"
