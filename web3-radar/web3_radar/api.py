from __future__ import annotations

import asyncio
import traceback
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web3_radar import db
from web3_radar.collectors.airdrop import scan_airdrops
from web3_radar.collectors.ambassador import scan_ambassadors
from web3_radar.collectors.binance import BinanceClient
from web3_radar.collectors.launch import scan_launches
from web3_radar.collectors.meme import scan_meme_coins
from web3_radar.config import STATIC_DIR, load_settings, save_settings
from web3_radar.engine.signals import analyze_klines
from web3_radar.wallet import enqueue_participate, wallet_status

app = FastAPI(title="链上雷达", version="1.0.0")
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
    return {"ok": True, "app": "链上雷达"}


@app.get("/api/settings")
async def get_settings() -> dict[str, Any]:
    return load_settings()


@app.post("/api/settings")
async def post_settings(body: SettingsBody) -> dict[str, Any]:
    current = load_settings()
    current.update(body.settings)
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
    items = await client.top100_perp_by_market_cap()
    _universe_cache = items
    await db.cache_set("universe", items, 60 * 30)
    return {"items": items, "cached": False}


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


@app.post("/api/contracts/analyze")
async def analyze_contracts(body: AnalyzeBody) -> dict[str, Any]:
    settings = load_settings()
    interval = body.interval or settings.get("kline_interval") or "4h"
    n_sims = int(body.n_sims or settings.get("monte_carlo_sims") or 1_000_000)
    job_id = f"job-{int(asyncio.get_event_loop().time()*1000)}"
    _jobs[job_id] = {"status": "running", "done": 0, "total": 0, "results": [], "error": ""}

    async def runner() -> None:
        client = BinanceClient()
        try:
            universe = _universe_cache or (await db.cache_get("universe")) or []
            if not universe:
                uni = await contract_universe()
                universe = uni["items"]
            symbols = body.symbols or [u["binance_symbol"] for u in universe]
            _jobs[job_id]["total"] = len(symbols)
            meta = {u["binance_symbol"]: u for u in universe}
            sem = asyncio.Semaphore(6)

            async def one(sym: str):
                async with sem:
                    df = await client.klines(sym, interval=interval, limit=int(settings.get("kline_limit") or 500))
                    result = await asyncio.to_thread(
                        analyze_klines,
                        df,
                        sym,
                        n_sims,
                        float(settings.get("signal_threshold") or 0.18),
                        float(settings.get("atr_sl_mult") or 1.5),
                        float(settings.get("atr_tp_mult") or 2.5),
                        None,
                        float(settings.get("monte_carlo_top_pct") or 1.0),
                    )
                    extra = meta.get(sym, {})
                    result["name"] = extra.get("name") or sym
                    result["market_cap"] = extra.get("market_cap")
                    result["market_cap_rank"] = extra.get("market_cap_rank")
                    result["venue"] = extra.get("venue") or ""
                    result["key"] = sym
                    return result

            tasks = [asyncio.create_task(one(s)) for s in symbols]
            for fut in asyncio.as_completed(tasks):
                try:
                    res = await fut
                    _jobs[job_id]["results"].append(res)
                except Exception as exc:
                    _jobs[job_id]["results"].append({"symbol": "?", "decision": "观望", "error": str(exc)})
                _jobs[job_id]["done"] += 1
            _jobs[job_id]["status"] = "done"
        except Exception as exc:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = f"{exc}\n{traceback.format_exc()}"

    asyncio.create_task(runner())
    return {"job_id": job_id}


@app.get("/api/contracts/analyze/{job_id}")
async def analyze_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    results = await _attach_marks("contract", job.get("results") or [])
    return {**job, "results": results}


@app.get("/api/meme")
async def meme() -> dict[str, Any]:
    settings = load_settings()
    cached = await db.cache_get("meme")
    if cached:
        cached["items"] = await _attach_marks("meme", cached.get("items") or [])
        cached["cached"] = True
        return cached
    data = await scan_meme_coins(
        min_liquidity_usd=float(settings.get("meme_min_liquidity_usd") or 20_000),
        min_unique_buyers=int(settings.get("meme_min_unique_buyers") or 8),
        min_holder_growth=int(settings.get("meme_min_holder_growth") or 5),
    )
    await db.cache_set("meme", data, 120)
    data["items"] = await _attach_marks("meme", data.get("items") or [])
    data["cached"] = False
    return data


@app.get("/api/ambassadors")
async def ambassadors() -> dict[str, Any]:
    settings = load_settings()
    cached = await db.cache_get("ambassadors")
    if cached:
        cached["items"] = await _attach_marks("ambassador", cached.get("items") or [])
        cached["cached"] = True
        return cached
    data = await scan_ambassadors(
        twitter_bearer=str(settings.get("twitter_bearer_token") or ""),
        lookback_days=int(settings.get("ambassador_lookback_days") or 7),
    )
    await db.cache_set("ambassadors", data, 300)
    data["items"] = await _attach_marks("ambassador", data.get("items") or [])
    return data


@app.get("/api/launches")
async def launches() -> dict[str, Any]:
    settings = load_settings()
    cached = await db.cache_get("launches")
    if cached:
        cached["items"] = await _attach_marks("launch", cached.get("items") or [])
        cached["cached"] = True
        return cached
    data = await scan_launches(twitter_bearer=str(settings.get("twitter_bearer_token") or ""), lookback_days=5)
    await db.cache_set("launches", data, 180)
    data["items"] = await _attach_marks("launch", data.get("items") or [])
    return data


@app.get("/api/airdrops")
async def airdrops() -> dict[str, Any]:
    settings = load_settings()
    cached = await db.cache_get("airdrops")
    if cached:
        cached["items"] = await _attach_marks("airdrop", cached.get("items") or [])
        cached["cached"] = True
        return cached
    data = await scan_airdrops(min_funding_usd=float(settings.get("airdrop_min_funding_usd") or 20_000_000))
    await db.cache_set("airdrops", data, 3600)
    data["items"] = await _attach_marks("airdrop", data.get("items") or [])
    return data


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


