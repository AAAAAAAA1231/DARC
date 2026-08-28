@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 正在启动开盘建议，浏览器打开后请稍等行情计算…
python.exe -m market_advisor --web --per-market 40
if errorlevel 1 (
  echo.
  echo 启动失败。请把上面的报错发回来。
  pause
)
