from __future__ import annotations

import asyncio
import traceback
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web3_radar import copytrade
from web3_radar import db
from web3_radar.collectors.airdrop import scan_airdrops
from web3_radar.collectors.ambassador import scan_ambassadors
from web3_radar.collectors.binance import BinanceClient, builtin_markets, resolve_perp_symbol, select_perp_universe
from web3_radar.collectors.launch import scan_launches
from web3_radar.collectors.meme import scan_meme_coins
from web3_radar.collectors.news import scan_news
from web3_radar.config import (
    INITIAL_INDICATOR_SHARES,
    MONTE_CARLO_SIMS,
    STATIC_DIR,
    format_sim_count,
    load_settings,
    save_settings,
)
from web3_radar.engine.indicators import historical_expectancy
from web3_radar.engine.live_learn import LEDGER_KEY, LEDGER_TTL, apply_live_feedback, attach_win_rates
from web3_radar.engine.signals import (
    analyze_klines,
    average_weights_from_results,
    fit_global_weights,
    mark_top_recommendations,
)
from web3_radar.wallet import enqueue_participate, wallet_status


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    import sys

    stop = asyncio.Event()

    async def _watch_loop() -> None:
        await asyncio.sleep(20)
        from web3_radar.collectors.launch_watch import apply_due_entries, scan_watch_accounts

        while not stop.is_set():
            try:
                settings = load_settings()
                data = await scan_watch_accounts(str(settings.get("twitter_bearer_token") or ""))
                await apply_due_entries(data.get("items") or [])
            except Exception:
                pass
            try:
                await asyncio.wait_for(stop.wait(), timeout=45)
            except asyncio.TimeoutError:
                continue

    task = None
    if "pytest" not in sys.modules:
        task = asyncio.create_task(_watch_loop())
    try:
        yield
    finally:
        stop.set()
        if task:
            task.cancel()


app = FastAPI(title="链上雷达", version="1.3.1", lifespan=_lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_jobs: dict[str, dict[str, Any]] = {}
_universe_cache: list[dict[str, Any]] = []


class MarkBody(BaseModel):
    category: str
    item_key: str
    status: str
    note: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class SettingsBody(BaseModel):
    settings: dict[str, Any]


class AnalyzeBody(BaseModel):
    symbols: list[str] | None = None
    interval: str | None = None
    n_sims: int | None = None
    mode: str = "auto"  # auto | fit | infer


class AnalyzeOneBody(BaseModel):
    symbol: str
    interval: str | None = None


class ParticipateBody(BaseModel):
    category: str
    item: dict[str, Any]
    auto: bool = False


class WalletConnectBody(BaseModel):
    address: str
    chain: str = "ethereum"


class TaskUpdateBody(BaseModel):
    status: str
    tx_hash: str = ""
    error: str = ""


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/wallet")
async def wallet_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "wallet.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": "链上雷达", "version": "1.3.1"}


@app.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    return load_settings()


@app.post("/api/settings")
async def post_settings(body: SettingsBody) -> dict[str, Any]:
    incoming = dict(body.settings or {})
    for key in incoming:
        low = str(key).lower()
        if any(bit in low for bit in ("private_key", "privatekey", "mnemonic", "seed_phrase", "助记词")):
            raise HTTPException(400, "不会收取或保存私钥、助记词。链上买入卖出请用钱包确认。")
    current = load_settings()
    current.update(incoming)
    save_settings(current)
    return current


@app.get("/api/marks")
async def get_marks(category: str | None = None) -> list[dict[str, Any]]:
    return await db.list_marks(category)


@app.post("/api/marks")
async def post_mark(body: MarkBody) -> dict[str, Any]:
    return await db.upsert_mark(body.category, body.item_key, body.status, body.note, body.extra)


@app.get("/api/contracts/universe")
async def contract_universe() -> dict[str, Any]:
    global _universe_cache
    cached = await db.cache_get("universe")
    if cached:
        _universe_cache = cached
        return {"items": cached, "cached": True}
    client = BinanceClient()
    note = ""
    stale = False
    try:
        items = await client.top100_perp_by_market_cap()
    except Exception as exc:
        stale_items = await db.cache_get("universe", allow_expired=True)
        if stale_items:
            _universe_cache = stale_items
            return {
                "items": stale_items,
                "cached": True,
                "stale": True,
                "note": "行情源限流，沿用上次标的名单",
                "error": str(exc),
            }
        items = select_perp_universe(builtin_markets(), set(), set())
        note = "行情源限流，已用内置前排合约名单继续分析"
        stale = True
    _universe_cache = items
    await db.cache_set("universe", items, 60 * 60 * 6)
    return {"items": items, "cached": False, "stale": stale, "note": note}


def _sort_contract_results(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(r: dict[str, Any]) -> tuple[float, float, float, float]:
        if r.get("error") or not r.get("symbol") or r.get("symbol") == "?":
            return (-1.0, -1.0, 0.0, 0.0)
        rec = 1.0 if r.get("recommend") else 0.0
        wr = float(r.get("win_rate") or 0.0)
        score = float(r.get("score") or 0.0)
        return (rec, wr, abs(score), score)

    return sorted(rows or [], key=key, reverse=True)


def _finalize_contract_results(
    rows: list[dict[str, Any]],
    *,
    already_marked: bool = False,
    n: int = 3,
    skip_symbols: list[str] | None = None,
) -> list[dict[str, Any]]:
    rows = list(rows or [])
    if already_marked:
        return _sort_contract_results(rows)
    return _sort_contract_results(mark_top_recommendations(rows, n, skip_symbols=skip_symbols))


async def _attach_marks(category: str, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    marks = await db.marks_map(category)
    out = []
    for it in items:
        key = str(it.get("key") or it.get("binance_symbol") or "")
        m = marks.get(key, {})
        row = dict(it)
        row["mark_status"] = m.get("status") or "none"
        row["mark_note"] = m.get("note") or ""
        out.append(row)
    return out


def _running_analyze_job(kind: str | None = None) -> tuple[str, dict[str, Any]] | tuple[None, None]:
    for jid, job in _jobs.items():
        if job.get("status") != "running":
            continue
        if kind and job.get("kind") != kind:
            continue
        return jid, job
    return None, None


async def _ensure_fitted_model() -> dict[str, Any] | None:
    model = await db.load_fitted_model()
    if model and model.get("weights") and int(model.get("n_sims") or 0) >= MONTE_CARLO_SIMS:
        return model
    last = await db.latest_analysis_run()
    if not last:
        return model
    weights = average_weights_from_results(last.get("results") or [])
    n_sims = int(last.get("n_sims") or 0)
    if weights and n_sims >= MONTE_CARLO_SIMS:
        model = {
            "weights": weights,
            "n_sims": n_sims,
            "fitted_at": last.get("created_at"),
            "interval": "",
            "source": "migrated_from_last_run",
            "sample_count": len(last.get("results") or []),
        }
        await db.save_fitted_model(model)
        return model
    return model


def _model_note(model: dict[str, Any] | None) -> str:
    if not model or not model.get("weights"):
        return f"尚未完成权重拟合。先做一次 {format_sim_count(MONTE_CARLO_SIMS)}校准，之后刷新按实盘涨跌回写权重。"
    when = str(model.get("fitted_at") or "")[:19]
    n = int(model.get("n_sims") or 0)
    live = str(model.get("live_updated_at") or "")[:19]
    live_txt = f"最近一次按推荐盈亏回写于 {live}。" if live else "每次刷新会按上次推荐的涨跌和时间衰减回写权重。"
    return (
        f"权重已于 {when} 用 {n:,} 次模拟校准。{live_txt}"
        "刷新会立刻重算全部标的，按各币胜率给出推荐，不再因为未到期持仓而跳过。"
    )


@app.post("/api/contracts/analyze")
async def analyze_contracts(body: AnalyzeBody) -> dict[str, Any]:
    settings = load_settings()
    interval = body.interval or settings.get("kline_interval") or "4h"
    n_sims = int(body.n_sims or settings.get("monte_carlo_sims") or MONTE_CARLO_SIMS)
    requested = (body.mode or "auto").strip().lower()
    model = await _ensure_fitted_model()
    has_model = bool(model and model.get("weights") and int(model.get("n_sims") or 0) >= MONTE_CARLO_SIMS)
    if requested == "auto":
        kind = "infer" if has_model else "fit"
    elif requested == "infer":
        kind = "infer" if has_model else "fit"
    else:
        kind = "fit"

    running_id, running = _running_analyze_job()
    if running_id and running:
        # Never start a second full-universe job; prefer the in-flight one.
        return {
            "job_id": running_id,
            "reused": True,
            "kind": running.get("kind") or kind,
            "done": running.get("done"),
            "total": running.get("total"),
        }

    job_id = f"job-{int(asyncio.get_event_loop().time()*1000)}"
    _jobs[job_id] = {
        "status": "running",
        "kind": kind,
        "done": 0,
        "total": 0,
        "results": [],
        "error": "",
        "interval": interval,
        "n_sims": n_sims,
        "phase": "收集K线" if kind == "fit" else "套用模型",
    }

    async def runner() -> None:
        client = BinanceClient()
        try:
            universe = _universe_cache or (await db.cache_get("universe")) or []
            if not universe:
                uni = await contract_universe()
                universe = uni["items"]
            symbols = body.symbols or [u["binance_symbol"] for u in universe]
            _jobs[job_id]["total"] = max(len(symbols) * 2, 1)
            meta = {u["binance_symbol"]: u for u in universe}
            sem = asyncio.Semaphore(6)
            threshold = float(settings.get("signal_threshold") or 0.18)
            sl_m = float(settings.get("atr_sl_mult") or 1.5)
            tp_m = float(settings.get("atr_tp_mult") or 2.5)
            top_pct = float(settings.get("monte_carlo_top_pct") or 1.0)
            klimit = int(settings.get("kline_limit") or 500)

            async def fetch_one(sym: str):
                async with sem:
                    df = await client.klines(sym, interval=interval, limit=klimit)
                    return sym, df

            frames: dict[str, Any] = {}
            fetch_tasks = [asyncio.create_task(fetch_one(s)) for s in symbols]
            for fut in asyncio.as_completed(fetch_tasks):
                try:
                    sym, df = await fut
                    frames[sym] = df
                except Exception as exc:
                    _jobs[job_id]["results"].append({"symbol": "?", "decision": "观望", "error": str(exc)})
                _jobs[job_id]["done"] += 1
                _jobs[job_id]["phase"] = f"已取K线 {_jobs[job_id]['done']}/{len(symbols)}"

            weights = None
            fitted_snapshot = dict(model or {})
            if kind == "fit":
                _jobs[job_id]["phase"] = f"{format_sim_count(n_sims)}权重校准"
                expect_maps = []
                names: list[str] = list(INITIAL_INDICATOR_SHARES)
                # Median across top names is enough; walking every coin's history is too slow for a global model.
                for _sym, df in list(frames.items())[:25]:
                    try:
                        emap = await asyncio.to_thread(historical_expectancy, df)
                        if emap:
                            expect_maps.append(emap)
                            names = list(emap.keys())
                    except Exception:
                        continue

                def _on_mc_progress(done: int, total: int) -> None:
                    pct = int(done * 100 / max(total, 1))
                    _jobs[job_id]["phase"] = (
                        f"{format_sim_count(total)}权重校准 {done:,}/{total:,}（{pct}%）"
                    )

                prior = None
                if model and isinstance(model.get("weights"), dict) and model.get("weights"):
                    prior = model["weights"]
                elif isinstance(settings.get("fitted_indicator_weights"), dict):
                    prior = settings.get("fitted_indicator_weights")

                weights = await asyncio.to_thread(
                    fit_global_weights,
                    expect_maps,
                    names,
                    prior,
                    n_sims,
                    top_pct,
                    None,
                    on_progress=_on_mc_progress,
                )
                from datetime import datetime, timezone

                model_out = {
                    "weights": weights,
                    "n_sims": n_sims,
                    "fitted_at": datetime.now(timezone.utc).isoformat(),
                    "interval": interval,
                    "source": "global_monte_carlo",
                    "sample_count": len(expect_maps),
                    "expectancies": {},
                }
                await db.save_fitted_model(model_out)
                current_settings = load_settings()
                current_settings["monte_carlo_sims"] = n_sims
                current_settings["fitted_indicator_weights"] = weights
                save_settings(current_settings)
                _jobs[job_id]["model"] = {"n_sims": n_sims, "fitted_at": model_out["fitted_at"], "sample_count": len(expect_maps)}
                fitted_snapshot = model_out
            else:
                weights = (model or {}).get("weights") or {}
                fitted_snapshot = dict(model or {})

            _jobs[job_id]["phase"] = "套用模型出信号"
            _jobs[job_id]["results"] = [r for r in _jobs[job_id]["results"] if r.get("error")]

            async def score_one(sym: str, df):
                result = await asyncio.to_thread(
                    analyze_klines,
                    df,
                    sym,
                    n_sims,
                    threshold,
                    sl_m,
                    tp_m,
                    None,
                    top_pct,
                    weights,
                )
                extra = meta.get(sym, {})
                result["name"] = extra.get("name") or sym
                result["market_cap"] = extra.get("market_cap")
                result["market_cap_rank"] = extra.get("market_cap_rank")
                result["venue"] = extra.get("venue") or ""
                result["key"] = sym
                return result

            score_tasks = [asyncio.create_task(score_one(sym, df)) for sym, df in frames.items()]
            for fut in asyncio.as_completed(score_tasks):
                try:
                    res = await fut
                    _jobs[job_id]["results"].append(res)
                except Exception as exc:
                    _jobs[job_id]["results"].append({"symbol": "?", "decision": "观望", "error": str(exc)})
                _jobs[job_id]["done"] += 1

            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["n_sims"] = n_sims
            ledger = await db.cache_get(LEDGER_KEY) or {}
            learned = apply_live_feedback(
                _jobs[job_id].get("results") or [],
                ledger,
                weights or {},
                interval,
                threshold=threshold,
            )
            _jobs[job_id]["results"] = _sort_contract_results(learned["results"])
            _jobs[job_id]["recommend_final"] = True
            _jobs[job_id]["recommend_n"] = learned.get("recommend_n")
            _jobs[job_id]["live_learn"] = learned.get("summary")
            await db.cache_set(LEDGER_KEY, learned["ledger"], LEDGER_TTL)
            if learned.get("weights_changed") and learned.get("weights"):
                from datetime import datetime, timezone

                live_model = dict(fitted_snapshot or {})
                live_model["weights"] = learned["weights"]
                live_model["n_sims"] = int(live_model.get("n_sims") or n_sims)
                live_model["live_updated_at"] = datetime.now(timezone.utc).isoformat()
                live_model["live_source"] = "recommendation_pnl"
                await db.save_fitted_model(live_model)
                current_settings = load_settings()
                current_settings["fitted_indicator_weights"] = learned["weights"]
                save_settings(current_settings)
            await db.save_analysis_run(_jobs[job_id])
        except Exception as exc:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = f"{exc}\n{traceback.format_exc()}"

    asyncio.create_task(runner())
    return {"job_id": job_id, "kind": kind, "reused": False}


@app.post("/api/contracts/analyze-one")
async def analyze_one_contract(body: AnalyzeOneBody) -> dict[str, Any]:
    settings = load_settings()
    interval = body.interval or settings.get("kline_interval") or "4h"
    n_sims = int(settings.get("monte_carlo_sims") or MONTE_CARLO_SIMS)
    model = await _ensure_fitted_model()
    weights = (model or {}).get("weights") if model else None
    if not weights:
        raise HTTPException(400, "尚未拟合权重。请先点「刷新信号」完成一次校准，再分析单一币种。")
    universe = _universe_cache or (await db.cache_get("universe")) or []
    try:
        symbol, meta = resolve_perp_symbol(body.symbol, universe)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    client = BinanceClient()
    klimit = int(settings.get("kline_limit") or 500)
    threshold = float(settings.get("signal_threshold") or 0.18)
    sl_m = float(settings.get("atr_sl_mult") or 1.5)
    tp_m = float(settings.get("atr_tp_mult") or 2.5)
    top_pct = float(settings.get("monte_carlo_top_pct") or 1.0)
    df = None
    last_err = ""
    tried = [symbol]
    if symbol.endswith("USDT") and not symbol.startswith("1000"):
        tried.append("1000" + symbol)
    for cand in tried:
        try:
            df = await client.klines(cand, interval=interval, limit=klimit)
            symbol = cand
            break
        except Exception as exc:
            last_err = str(exc)
            df = None
    if df is None or len(df) < 60:
        raise HTTPException(404, f"找不到 {body.symbol} 的K线（已试 {', '.join(tried)}）。{last_err}")
    result = await asyncio.to_thread(
        analyze_klines,
        df,
        symbol,
        n_sims,
        threshold,
        sl_m,
        tp_m,
        None,
        top_pct,
        weights,
    )
    extra = meta if str(meta.get("binance_symbol") or "").upper() == symbol else {}
    if not extra:
        extra = next((u for u in universe if str(u.get("binance_symbol") or "").upper() == symbol), {}) or meta
    result["name"] = extra.get("name") or symbol
    result["market_cap"] = extra.get("market_cap")
    result["market_cap_rank"] = extra.get("market_cap_rank")
    result["venue"] = extra.get("venue") or ""
    result["key"] = symbol
    result["single_coin"] = True
    ledger = await db.cache_get(LEDGER_KEY) or {}
    attach_win_rates([result], ledger.get("closed") or [])
    result["recommend"] = str(result.get("decision") or "") in ("涨", "跌")
    return result


@app.get("/api/contracts/analyze/{job_id}")
async def analyze_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    results = await _attach_marks(
        "contract",
        _finalize_contract_results(
            job.get("results") or [],
            already_marked=bool(job.get("recommend_final")),
            n=int(job.get("recommend_n") or 3),
        ),
    )
    return {**job, "results": results}


@app.get("/api/contracts/status")
async def contracts_fit_status() -> dict[str, Any]:
    running_id, running = _running_analyze_job()
    model = await _ensure_fitted_model()
    fitted = bool(model and model.get("weights") and int(model.get("n_sims") or 0) >= MONTE_CARLO_SIMS)
    model_pub = None
    if model:
        model_pub = {k: model.get(k) for k in ("n_sims", "fitted_at", "source", "sample_count", "interval", "live_updated_at")}
    if running_id and running:
        kind = running.get("kind") or "fit"
        return {
            "fitted": fitted,
            "running": True,
            "job_id": running_id,
            "kind": kind,
            "done": running.get("done") or 0,
            "total": running.get("total") or 0,
            "phase": running.get("phase") or "",
            "model": model_pub,
            "fitted_note": (
                f"{'正在校准权重' if kind == 'fit' else '正在套用模型'} "
                f"{running.get('done') or 0}/{running.get('total') or 0}"
                + (f" · {running.get('phase')}" if running.get("phase") else "")
            ),
            "results": await _attach_marks("contract", _finalize_contract_results(running.get("results") or [])),
        }
    last = await db.latest_analysis_run()
    last_rows = (last or {}).get("results") or []
    results = await _attach_marks(
        "contract",
        _finalize_contract_results(
            last_rows,
            already_marked=any("recommend" in r for r in last_rows),
        ),
    )
    payload = {
        "fitted": fitted,
        "running": False,
        "kind": "infer" if fitted else "",
        "model": model_pub,
        "fitted_note": _model_note(model),
        "results": results,
    }
    if last:
        payload.update(
            {
                "created_at": last.get("created_at"),
                "up_count": last.get("up_count"),
                "down_count": last.get("down_count"),
                "wait_count": last.get("wait_count"),
                "n_sims": last.get("n_sims"),
            }
        )
    return payload


async def _scan_or_cache(cache_key: str, category: str, ttl: int, refresh: bool, producer):
    if not refresh:
        cached = await db.cache_get(cache_key)
        if cached and cached.get("items"):
            cached["items"] = await _attach_marks(category, cached.get("items") or [])
            cached["cached"] = True
            return cached
    try:
        data = await asyncio.wait_for(producer(), timeout=55)
    except Exception as exc:
        data = {"items": [], "count": 0, "errors": [str(exc)]}
    data.setdefault("errors", [])
    data.setdefault("items", [])
    data["count"] = len(data.get("items") or [])
    if data["items"]:
        payload = dict(data)
        payload["items"] = [ {k: v for k, v in it.items() if k not in ("mark_status", "mark_note")} for it in payload["items"] ]
        await db.cache_set(cache_key, payload, ttl)
    data["items"] = await _attach_marks(category, data.get("items") or [])
    data["cached"] = False
    return data


@app.get("/api/meme")
async def meme(refresh: bool = Query(False)) -> dict[str, Any]:
    settings = load_settings()
    data = await _scan_or_cache(
        "meme_v5",
        "meme",
        90,
        refresh,
        lambda: scan_meme_coins(
            min_liquidity_usd=float(settings.get("meme_min_liquidity_usd") or 1_000_000),
            min_unique_buyers=int(settings.get("meme_min_unique_buyers") or 8),
            min_holder_growth=int(settings.get("meme_min_holder_growth") or 5),
            twitter_bearer=str(settings.get("twitter_bearer_token") or ""),
        ),
    )
    try:
        data["copytrade"] = await copytrade.evaluate_memes(
            data.get("items") or [],
            open_new=not data.get("cached"),
        )
    except Exception as exc:
        data.setdefault("errors", []).append(f"copytrade: {exc}")
    return data


@app.get("/api/ambassadors")
async def ambassadors(refresh: bool = Query(False)) -> dict[str, Any]:
    settings = load_settings()
    return await _scan_or_cache(
        "ambassadors_v6",
        "ambassador",
        300,
        refresh,
        lambda: scan_ambassadors(
            twitter_bearer=str(settings.get("twitter_bearer_token") or ""),
            lookback_days=int(settings.get("ambassador_lookback_days") or 7),
        ),
    )


@app.get("/api/launches")
async def launches(refresh: bool = Query(False)) -> dict[str, Any]:
    settings = load_settings()
    return await _scan_or_cache(
        "launches_v16",
        "launch",
        180,
        refresh,
        lambda: scan_launches(twitter_bearer=str(settings.get("twitter_bearer_token") or ""), lookback_days=30),
    )


@app.get("/api/cycle")
async def cycle(refresh: bool = Query(False)) -> dict[str, Any]:
    cached = None if refresh else await db.cache_get("cycle_v1")
    if isinstance(cached, dict) and cached.get("phase"):
        return cached
    from web3_radar.engine.cycle import assess_cycle, attach_cycle_trade

    df = None
    errors: list[str] = []
    try:
        client = BinanceClient()
        df = await client.klines("BTCUSDT", interval="1d", limit=800)
    except Exception as exc:
        errors.append(f"BTC 日线: {exc}")
        df = None
    data = assess_cycle(df)
    last = await db.latest_analysis_run()
    data["trade"] = attach_cycle_trade(data, (last or {}).get("results") or [])
    data["errors"] = errors
    await db.cache_set("cycle_v1", data, 600)
    return data


class LaunchWatchBody(BaseModel):
    handle: str
    note: str = ""


@app.get("/api/launch-watches")
async def get_launch_watches() -> dict[str, Any]:
    from web3_radar.collectors.launch_watch import scan_watch_accounts

    settings = load_settings()
    return await scan_watch_accounts(str(settings.get("twitter_bearer_token") or ""))


@app.post("/api/launch-watches")
async def post_launch_watch(body: LaunchWatchBody) -> dict[str, Any]:
    from web3_radar.collectors.launch_watch import add_watch

    try:
        item = await add_watch(body.handle, body.note)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await db.cache_delete("launches_v16")
    return item


@app.post("/api/launch-watches/remove")
async def remove_launch_watch(body: LaunchWatchBody) -> dict[str, Any]:
    from web3_radar.collectors.launch_watch import remove_watch

    await remove_watch(body.handle)
    await db.cache_delete("launches_v16")
    return {"ok": True}


@app.get("/api/news")
async def news(refresh: bool = Query(False)) -> dict[str, Any]:
    return await _scan_or_cache("news_v3", "news", 90, refresh, scan_news)


@app.get("/api/airdrops")
async def airdrops(refresh: bool = Query(False)) -> dict[str, Any]:
    settings = load_settings()
    return await _scan_or_cache(
        "airdrops_v5",
        "airdrop",
        3600,
        refresh,
        lambda: scan_airdrops(
            min_funding_usd=float(settings.get("airdrop_min_funding_usd") or 20_000_000),
            btc_min_funding_usd=float(settings.get("airdrop_btc_min_funding_usd") or 5_000_000),
            twitter_bearer=str(settings.get("twitter_bearer_token") or ""),
        ),
    )


@app.get("/api/wallet")
async def get_wallet() -> dict[str, Any]:
    status = wallet_status()
    status["tasks"] = await db.list_wallet_tasks()
    return status


@app.post("/api/wallet/connect")
async def connect_wallet(body: WalletConnectBody) -> dict[str, Any]:
    settings = load_settings()
    settings["wallet_address"] = body.address
    settings["wallet_chain"] = body.chain
    save_settings(settings)
    return wallet_status()


@app.post("/api/wallet/disconnect")
async def disconnect_wallet() -> dict[str, Any]:
    settings = load_settings()
    settings["wallet_address"] = ""
    save_settings(settings)
    return wallet_status()


@app.post("/api/wallet/participate")
async def participate(body: ParticipateBody) -> dict[str, Any]:
    try:
        task = await enqueue_participate(body.category, body.item, auto=body.auto)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return task


@app.post("/api/wallet/tasks/{task_id}")
async def update_task(task_id: int, body: TaskUpdateBody) -> dict[str, Any]:
    await db.update_wallet_task(task_id, status=body.status, tx_hash=body.tx_hash, error=body.error)
    return {"ok": True}


class AmbassadorAddBody(BaseModel):
    project: str
    text: str = ""
    url: str = ""
    deadline: str = ""


class CopySettingsBody(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


@app.post("/api/ambassadors")
async def add_ambassador(body: AmbassadorAddBody) -> dict[str, Any]:
    project = (body.project or "").strip()
    if not project:
        raise HTTPException(400, "请填写项目名")
    from datetime import datetime, timezone

    item = {
        "key": f"manual:{project.lower()}:{int(datetime.now(timezone.utc).timestamp())}",
        "project": project,
        "username": "",
        "title": project,
        "text": body.text.strip() or f"手动加入观察：{project}",
        "url": body.url.strip(),
        "deadline": body.deadline.strip() or "一周内（手动）",
        "priority": "中",
        "priority_detail": "中 · 手动添加",
        "score": 50,
        "source": "手动",
        "source_kind": "manual",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manual = await db.cache_get("manual_ambassadors") or []
    if not isinstance(manual, list):
        manual = []
    manual.insert(0, item)
    await db.cache_set("manual_ambassadors", manual, 365 * 24 * 3600)
    await db.cache_delete("ambassadors_v2")
    await db.cache_delete("ambassadors_v3")
    await db.cache_delete("ambassadors_v6")
    await db.upsert_mark("ambassador", item["key"], "watching", "手动添加", item)
    return item


@app.get("/api/copytrade")
async def get_copytrade() -> dict[str, Any]:
    return await copytrade.snapshot()


@app.post("/api/copytrade/settings")
async def post_copytrade(body: CopySettingsBody) -> dict[str, Any]:
    return await copytrade.update_settings(body.settings)


@app.post("/api/copytrade/tick")
async def tick_copytrade() -> dict[str, Any]:
    data = await meme(refresh=False)
    return data.get("copytrade") or await copytrade.snapshot()


