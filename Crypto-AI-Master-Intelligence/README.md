# Crypto-AI-Master-Intelligence

Windows desktop intelligence terminal: **data → analysis → prediction → user action → actual result → P&L → review → new model version**.

This is not a demo, not a price ticker, and not a live trading bot. The process never places exchange orders and never stores private keys or seed phrases.

Statistical outputs are **not** deterministic forecasts. Simulation path count is **not** accuracy.

## System architecture

```
React (Vite + Tailwind + ECharts)
        │  /api
        ▼
FastAPI  → services → DataProvider registry → Binance / CoinGecko / GoPlus / DexScreener / DefiLlama / GitHub / TheSportsDB / lottery
                 │
                 ├─ SQLite (PostgreSQL-ready URL)
                 ├─ strategy plugins (14)
                 ├─ walk-forward backtest
                 └─ chunked NumPy Monte Carlo jobs
```

Desktop EXE: FastAPI + built UI + pywebview, packaged with PyInstaller (`build_exe.bat`).

## Features

| Module | What it does with live data |
| --- | --- |
| **50X Radar** | CoinGecko markets + GoPlus security hard-gate + multi-factor score. UNKNOWN ≠ SAFE. |
| **Futures** | Binance USDT-M **volume Top 100** (not a hardcoded BTC/ETH list), 14 strategies, Top 3 with entry/SL/TP. |
| **BTC cycle** | Halving calendar + 200D MA + ATH drawdown from Binance daily candles. MVRV/NUPL/SOPR stay UNKNOWN without an on-chain key. |
| **Spot** | Conservative / Balanced / Aggressive zones from live OHLCV. |
| **Airdrop** | DefiLlama protocols with TVL and no token symbol. Funding/valuation/EV = UNKNOWN unless sourced. |
| **Launch** | DexScreener search (launch/presale/IDO/TGE). Class A is keyword-based, not a fake VC database. |
| **Football** | Bundesliga, Serie A, La Liga via TheSportsDB. Poisson + Elo + Monte Carlo. Injuries/xG = UNKNOWN without a feed. |
| **Lottery** | SSQ / DLT history from official public APIs. Architecture for 3D / PL3 / PL5. Randomness disclaimer is mandatory. |
| **Portfolio** | User fills vs model recs vs results. Fees, funding, gas, slippage. Project status ≠ position status. |
| **Models** | Immutable versions, self-review, rollback, walk-forward OOS. |
| **Simulations** | 1M–10B paths, chunked, pause/resume/cancel. |
| **Alerts** | In-app + desktop + email/Telegram plugins (missing keys disable a channel). |

## Data sources

Copy `.env.example` to `.env`. Empty keys are valid: the UI shows `missing_key` / `UNKNOWN` instead of inventing rows.

Public market endpoints (Binance, CoinGecko, DexScreener, DefiLlama, GoPlus, TheSportsDB, lottery) work without secrets, subject to vendor rate limits.

## Environment

- Python 3.12+
- Node.js 18+ (UI build)
- Windows for the final EXE; Linux/macOS for development

## Install

```bash
cd Crypto-AI-Master-Intelligence
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
cd frontend && npm install && npm run build && cd ..
```

## Initialize database

The SQLite file is created on first API start (`data/cami.db`).

```bash
export PYTHONPATH=.
python -c "from backend.database.session import init_db; init_db()"
```

## Development

```bash
# terminal 1 — API
export PYTHONPATH=.
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8787

# terminal 2 — UI (optional; API also serves frontend/dist after build)
cd frontend && npm run dev
```

Windows: run `start.bat`.

Open `http://127.0.0.1:8787` (built UI) or `http://127.0.0.1:5173` (Vite proxy).

## Tests

```bash
export PYTHONPATH=.
python -m pytest backend/tests -q
cd frontend && npm test
```

Live provider tests hit real endpoints. If a vendor is down, they assert structured `SourceStatus` — they do not fake a successful book.

## EXE (Windows)

Double-click `dist\Crypto-AI-Master-Intelligence.exe` after building. A **boot splash** appears while the onefile EXE unpacks (first launch 1–3 minutes — this is not a freeze). Then a window loads the local API and the built UI at `http://127.0.0.1:8787` (port is required — opening `127.0.0.1` alone is `ERR_CONNECTION_REFUSED`). If the window component fails, the engine still starts and the default browser is opened. Failures write `logs\desktop.log` **next to the EXE**. SQLite (`data\cami.db`), logs, and `.env` are also created there. Missing API keys do not block launch.

```bat
build_exe.bat
```

Output: `dist\Crypto-AI-Master-Intelligence.exe`

This cloud/Linux environment cannot emit a PE `.exe`; GitHub Actions (`Build Windows EXE`) builds it on `windows-latest`. Place `.env` beside the EXE for optional keys. Never bake secrets into the binary.

## Security

- Secrets: environment only
- Logs redact key-like fields
- Public wallet addresses only
- Auto-trading is hard-off

## Models and learning loop

Each module has an active `model_*` version. Self-review writes a **new** version after enough settled outcomes; rollback reactivates an old row. Weights are regularized and capped to limit overfitting.

## Disclaimer

All scores, probabilities, entry zones, and simulations are statistical. They are not a promise of 50X, a guaranteed football result, or a lottery prize.
