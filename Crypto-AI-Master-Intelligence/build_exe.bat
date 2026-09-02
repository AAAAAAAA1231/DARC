@echo off
setlocal
cd /d %~dp0
call .venv\Scripts\activate
cd frontend
call npm install
call npm run build
cd ..
pip install pyinstaller pywebview
pyinstaller --noconfirm --clean ^
  --name Crypto-AI-Master-Intelligence ^
  --add-data "frontend/dist;frontend/dist" ^
  --add-data "config;config" ^
  --hidden-import backend.main ^
  --hidden-import backend.services.dashboard ^
  --hidden-import backend.data_sources.onchain ^
  --hidden-import uvicorn.logging ^
  --hidden-import uvicorn.protocols.http.auto ^
  --collect-all sklearn ^
  backend/desktop_app.py
echo EXE at dist\Crypto-AI-Master-Intelligence.exe
