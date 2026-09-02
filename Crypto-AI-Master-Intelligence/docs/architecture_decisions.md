# Architecture decisions — engineering choices made without blocking on low-value questions.

## A1. Location inside the existing repository

The workspace already contains the DARC protocol. This system is added as `Crypto-AI-Master-Intelligence/` so existing user code is not deleted or rewritten.

## A2. Desktop packaging: PyInstaller + pywebview, not Tauri as the primary path

The source of truth is a Python analytics backend (SQLAlchemy, NumPy, scikit-learn, Numba). Wrapping that in Tauri would still require a sidecar Python process. The EXE path is:

1. Build the React UI into `frontend/dist`
2. FastAPI serves `/api` and the static UI
3. `backend/desktop_app.py` opens a pywebview window
4. `build_exe.bat` runs PyInstaller to produce `dist/Crypto-AI-Master-Intelligence.exe`

Tauri remains optional later; it is not required for the Windows EXE acceptance path.

## A3. Database

SQLAlchemy 2.x with SQLite by default (`data/cami.db`). `CAMI_DATABASE_URL` can point at PostgreSQL without changing models. No ORM-level SQLite-only types are used.

## A4. Identity

`PROJECT-{CHAIN}-{CONTRACT}` when both exist (EVM addresses normalized to lowercase). Pre-token projects use `PROJECT-WEB-{sha256[:16]}` over website + X handle + name.

## A5. Public providers (no fabricated payloads)

Binance REST may return HTTP 451 from some cloud regions. The Binance adapter failovers to `www.binance.com` / `data-api.binance.vision` / `api.binance.us` and records the resolved host. This is still live Binance market data, not a mock.

| Domain | Provider | Auth |
| --- | --- | --- |
| Spot/Futures OHLCV, volume Top 100, funding, OI | Binance public REST | Optional key |
| Market cap / social / developer | CoinGecko | Optional Pro key |
| Token security | GoPlus | Optional app key |
| DEX liquidity | DexScreener | None |
| TVL / tokenless protocols | DefiLlama | None |
| Repo activity | GitHub | Optional token |
| Football (BL/SA/PD) | TheSportsDB (public demo key) + football-data.org | football-data requires key |
| Lottery SSQ/DLT/3D/PL3/PL5/QXC | Official cwl.gov.cn / sporttery.cn first; live failover to kaijiang.500.com XML then data.17500.cn text | None |
| BTC hashrate / tip height | mempool.space | None |
| Confirmed tx count | blockchain.info charts | None |
| BTC dominance / global mcap | CoinPaprika | None |

On-chain cycle valuation metrics (MVRV, NUPL, SOPR, Puell, ETF flow) stay `UNKNOWN` until a dedicated valuation provider is keyed. mempool.space / blockchain.info / CoinPaprika supply hashrate, height, tx count, and dominance only — they are not used as fake MVRV. UNKNOWN is displayed, never filled with invented numbers.

Lottery official hosts often return HTTP 403/WAF from cloud IPs. The adapter then reads **live historical draw files** from kaijiang.500.com (XML) and data.17500.cn (text). Those are still published draw records, not generated numbers.

Dashboard BTC cycle reuses a persisted snapshot for 90 minutes so the homepage is not blocked on 800 daily klines + on-chain extras. Charts load independently via `/api/market/klines`. Period PnL is current net minus the earliest `portfolio_snapshots` row in that window; `None` until a prior snapshot exists (not a fabricated zero).

## A6. No live trading, no private keys

The process never calls exchange order endpoints. Wallet fields store public addresses only.

## A7. 50X recommendation gate

`UNKNOWN != SAFE`. Only SAFE / LOW_RISK / MEDIUM_RISK / NATIVE_PROTOCOL may enter the recommendation pool. Native L1 assets without a token contract are `NATIVE_PROTOCOL`, not SAFE-by-default tokens.

## A8. Strategy weights

Fourteen plugins share a regularized dynamic blend (initial / historical / recent / regime) with min/max caps. A new model version is written on review; old versions remain for rollback.

## A9. Simulation scale

1M–10B paths are chunked NumPy (optional Numba/CUDA). A Python `for i in range(10_000_000_000)` loop is forbidden.
