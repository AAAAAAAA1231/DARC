# Progress

## Completed

- Project tree, Cursor rules, config, logging, identity, parsing
- SQLAlchemy schema for all core tables (SQLite, PostgreSQL-ready URL)
- Provider registry: Binance, CoinGecko, GoPlus, DexScreener, DefiLlama, GitHub, football-data.org, TheSportsDB, lottery, mempool.space, blockchain.info, CoinPaprika
- 50X radar with security hard-gate and multi-factor score
- Futures live Top 100 + 14 strategy plugins + Top 3
- BTC cycle from live klines + halving calendar; MVRV/NUPL/SOPR remain UNKNOWN
- Optional live extras: hashrate, block height, confirmed tx, BTC dominance
- Spot (Conservative/Balanced/Aggressive)
- Airdrop (DefiLlama tokenless TVL protocols; funding UNKNOWN)
- Launch/presale (DexScreener search; Class A is keyword-based, not a fake VC DB)
- Football Poisson+Elo+Monte Carlo for Bundesliga/Serie A/La Liga
- Lottery history with official-host-first + 500.com / 17500 failover; Monte Carlo disclaimer
- Portfolio fills with fees/gas/funding/slippage; project status independent of position
- Portfolio snapshots for today/week/month PnL (None until history exists)
- Holdings overlay on radar/spot/asset pages (cost / PnL vs model; never live orders)
- Dashboard live volume Top 3, last radar/futures/football, BTC candlesticks
- Asset detail `/assets/:symbol` with live klines
- Model versions, self-review, walk-forward backtest
- Simulation jobs start/pause/resume/cancel
- Notification channel plugins
- Scheduler: hourly BTC + portfolio; daily radar/airdrop/launch/lottery/football/review
- Module pages hydrate from last stored scan on first open (radar/futures/spot/airdrop/launch/football/lottery)
- Light/dark CSS variables; provider status on the header and Settings table
- React quant terminal, FastAPI, PyInstaller scripts

## In progress

- EXE smoke test must be run on Windows; this environment is Linux and produces the build recipe plus a runnable local server

## Test results

See the latest pytest / vitest run after this revision.

## Known limits

- CoinGecko free rate limits restrict per-scan `coin_detail` calls; radar therefore security-scans a budgeted subset and leaves other contracts UNKNOWN (excluded from the pool)
- football-data.org stays `missing_key` until `FOOTBALL_DATA_API_KEY` is set; TheSportsDB is the default live fixture source
- MVRV/NUPL/SOPR/ETF flow remain UNKNOWN without a paid on-chain valuation provider
- Intraday/week/month PnL series are not invented when snapshot history does not exist
- `www.cwl.gov.cn` / `webapi.sporttery.cn` may 403/WAF from cloud IPs; 500.com XML and 17500 text are live historical failovers
