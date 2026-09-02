# Progress

## Completed

- Project tree, Cursor rules, config, logging, identity, parsing
- SQLAlchemy schema for all core tables (SQLite, PostgreSQL-ready URL)
- Provider registry: Binance, CoinGecko, GoPlus, DexScreener, DefiLlama, GitHub, football-data.org, TheSportsDB, lottery
- 50X radar with security hard-gate and multi-factor score
- Futures live Top 100 + 14 strategy plugins + Top 3
- BTC cycle from live klines + halving calendar; on-chain metrics marked UNKNOWN
- Spot (Conservative/Balanced/Aggressive)
- Airdrop (DefiLlama tokenless TVL protocols; funding UNKNOWN)
- Launch/presale (DexScreener search; Class A is keyword-based, not a fake VC DB)
- Football Poisson+Elo+Monte Carlo for Bundesliga/Serie A/La Liga
- Lottery history + Monte Carlo disclaimer
- Portfolio fills with fees/gas/funding/slippage; project status independent of position
- Model versions, self-review, walk-forward backtest
- Simulation jobs start/pause/resume/cancel
- Notification channel plugins
- Scheduler (disabled in tests)
- React quant terminal, FastAPI, PyInstaller scripts

## In progress

- EXE smoke test must be run on Windows; this environment is Linux and produces the build recipe plus a runnable local server

## Test results

- `pytest backend/tests`: 25 passed after Binance geo-failover (`www.binance.com` when `api.binance.com` returns HTTP 451)
- `vitest`: 1 passed
- Live health: Binance, CoinGecko, GoPlus, DexScreener, DefiLlama, TheSportsDB = ok
- football-data.org = missing_key (expected without FOOTBALL_DATA_API_KEY)
- Lottery official SSQ host may return HTTP 403 from some cloud IPs; the provider reports the error instead of fabricating draws
- Frontend production build: `frontend/dist`

- CoinGecko free rate limits restrict per-scan `coin_detail` calls; radar therefore security-scans a budgeted subset and leaves other contracts UNKNOWN (excluded from the pool)
- football-data.org stays `missing_key` until `FOOTBALL_DATA_API_KEY` is set; TheSportsDB is the default live fixture source
- MVRV/NUPL/SOPR/ETF flow remain UNKNOWN without a paid on-chain provider
- Intraday/week/month PnL series are not invented when snapshot history does not exist
- `pl3`/`pl5`/`3d` lottery games are architected; live history is wired for SSQ and DLT first

## Test results

See the latest pytest / vitest run in the agent session after dependencies install.
