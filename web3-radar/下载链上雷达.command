#!/bin/bash
cd "$(dirname "$0")"
echo
echo "正在下载链上雷达 Mac 版，请稍等…"
echo
ARCH="$(uname -m)"
if [ "$ARCH" = "x86_64" ]; then
  URL="https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar-intel.dmg"
  OUT="ChainRadar-intel.dmg"
else
  URL="https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar.dmg"
  OUT="ChainRadar.dmg"
fi
if curl -L --retry 3 --fail -o "$OUT" "$URL"; then
  SIZE=$(wc -c < "$OUT" | tr -d ' ')
  if [ "${SIZE:-0}" -gt 1000000 ]; then
    echo "下载完成：$OUT"
    echo "双击打开镜像，把「链上雷达」拖进「应用程序」。"
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
