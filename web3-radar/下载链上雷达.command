#!/bin/bash
cd "$(dirname "$0")"
echo
echo "正在下载链上雷达，请稍等…"
echo
ARCH="$(uname -m)"
if [ "$ARCH" = "x86_64" ]; then
  URL="https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar-mac-intel.zip"
else
  URL="https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar-mac.zip"
fi
OUT="链上雷达.zip"
if curl -L --retry 3 --fail -o "$OUT" "$URL"; then
  SIZE=$(wc -c < "$OUT" | tr -d ' ')
  if [ "${SIZE:-0}" -gt 1000000 ]; then
    echo "下载完成。正在打开…"
    open "$OUT"
    exit 0
  fi
fi
echo
echo "自动下载失败。请把下面链接复制到浏览器地址栏回车："
echo "$URL"
echo
read -r -p "按回车键关闭…"
exit 1
