@echo off
setlocal
cd /d %~dp0
if not exist .venv python -m venv .venv
call .venv\Scripts\activate
pip install -r requirements.txt
if not exist .env copy .env.example .env
if not exist frontend\node_modules (
  cd frontend
  npm install
  npm run build
  cd ..
)
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8787
