@echo off
setlocal EnableExtensions
cd /d %~dp0

where python >nul 2>&1
if errorlevel 1 (
  echo Python is required. Install Python 3.12 from https://www.python.org/downloads/ and re-run.
  exit /b 1
)

if not exist .venv (
  python -m venv .venv
)
call .venv\Scripts\activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python -m pip install pyinstaller pywebview

where npm >nul 2>&1
if errorlevel 1 (
  echo Node.js/npm is required once to build the UI. Install from https://nodejs.org/
  exit /b 1
)
pushd frontend
call npm install
call npm run build
if errorlevel 1 (
  echo Frontend build failed.
  popd
  exit /b 1
)
popd

if not exist frontend\dist\index.html (
  echo frontend\dist is missing. The EXE will not have a UI.
  exit /b 1
)

pyinstaller --noconfirm --clean Crypto-AI-Master-Intelligence.spec
if errorlevel 1 (
  echo PyInstaller failed.
  exit /b 1
)

if exist dist\Crypto-AI-Master-Intelligence.exe (
  echo.
  echo Built: dist\Crypto-AI-Master-Intelligence.exe
  echo Put .env next to the EXE if you have API keys. Missing keys are OK.
  echo SQLite and logs are created beside the EXE on first launch.
  echo First open can take 1-3 minutes. If Edge says connection refused, read logs\desktop.log.
) else (
  echo Expected dist\Crypto-AI-Master-Intelligence.exe was not produced.
  exit /b 1
)
