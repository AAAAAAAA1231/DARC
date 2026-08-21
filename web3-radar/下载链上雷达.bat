@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo 正在下载链上雷达压缩包，请稍等（不用点网页小箭头）...
echo.
set "ZIP=%~dp0ChainRadar.zip"
curl.exe -L --retry 3 --fail -o "%ZIP%" "https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar.zip"
if errorlevel 1 goto RAW
for %%A in ("%ZIP%") do if %%~zA LSS 1000000 goto RAW
goto UNZIP
:RAW
echo 发行版链接不可用，改用仓库直链...
curl.exe -L --retry 3 --fail -o "%ZIP%" "https://github.com/AAAAAAAA1231/DARC/raw/cursor/web3-radar-desktop-d86a/web3-radar/dist/ChainRadar.zip"
if errorlevel 1 goto FAIL
for %%A in ("%ZIP%") do if %%~zA LSS 1000000 goto FAIL
:UNZIP
echo 正在解压...
powershell -NoProfile -Command "Expand-Archive -Force -Path '%ZIP%' -DestinationPath '%~dp0'"
if errorlevel 1 goto FAIL
echo.
echo 下载完成。请进入 ChainRadar 文件夹，双击 ChainRadar.exe
echo 不要只把 exe 单独拷走，否则 Windows 更容易误报。
echo.
pause
exit /b 0
:FAIL
echo.
echo 自动下载失败。请把下面链接复制到浏览器地址栏回车：
echo https://github.com/AAAAAAAA1231/DARC/releases/latest/download/ChainRadar.zip
echo 下完后解压，进入 ChainRadar 文件夹再双击 ChainRadar.exe
echo.
pause
exit /b 1
