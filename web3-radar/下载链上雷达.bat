@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo 正在下载链上雷达 EXE，请稍等（不用点网页小箭头）...
echo.
set "OUT=%~dp0ChainRadar.exe"
curl.exe -L --retry 3 --fail -o "%OUT%" "https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar.exe"
if errorlevel 1 goto RAW
for %%A in ("%OUT%") do if %%~zA LSS 1000000 goto RAW
goto OK
:RAW
echo 发行版链接不可用，改用仓库直链...
curl.exe -L --retry 3 --fail -o "%OUT%" "https://github.com/AAAAAAAA1231/DARC/raw/cursor/web3-radar-desktop-d86a/web3-radar/dist/ChainRadar.exe"
if errorlevel 1 goto FAIL
for %%A in ("%OUT%") do if %%~zA LSS 1000000 goto FAIL
:OK
echo.
echo 下载完成。请双击 ChainRadar.exe
echo.
pause
exit /b 0
:FAIL
echo.
echo 自动下载失败。请把下面链接复制到浏览器地址栏回车：
echo https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar.exe
echo.
pause
exit /b 1
