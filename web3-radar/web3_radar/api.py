from __future__ import annotations

import asyncio
import traceback
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from web3_radar import copytrade
from web3_radar import db
from web3_radar.collectors.airdrop import scan_airdrops
from web3_radar.collectors.ambassador import scan_ambassadors
from web3_radar.collectors.binance import BinanceClient
from web3_radar.collectors.launch import scan_launches
from web3_radar.collectors.meme import scan_meme_coins
from web3_radar.config import INITIAL_INDICATOR_SHARES, STATIC_DIR, load_settings, save_settings
from web3_radar.engine.risk import RiskConfig, apply_portfolio_overlay, path_expectancy
from web3_radar.engine.signals import analyze_klines, average_weights_from_results, fit_global_weights
from web3_radar.wallet import enqueue_participate, wallet_status

app = FastAPI(title="链上雷达", version="1.3.0")
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
    return {"ok": True, "app": "链上雷达", "version": "1.3.0"}


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


@app.get("/api/contracts/cycle")
async def contract_cycle() -> dict[str, Any]:
    from web3_radar.engine.cycle import current_cycle

    try:
        view = await asyncio.to_thread(current_cycle)
    except Exception as exc:
        raise HTTPException(502, f"四年周期数据暂时拉不到：{exc}") from exc
    return view.to_dict()


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
    if model and model.get("weights") and int(model.get("n_sims") or 0) >= 1_000_000:
        return model
    last = await db.latest_analysis_run()
    if not last:
        return model
    weights = average_weights_from_results(last.get("results") or [])
    n_sims = int(last.get("n_sims") or 0)
    if weights and n_sims >= 1_000_000:
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
        return "尚未完成权重拟合。先做一次 100 万次校准，之后刷新只套用模型出涨跌。"
    when = str(model.get("fitted_at") or "")[:19]
    n = int(model.get("n_sims") or 0)
    return f"权重已于 {when} 用 {n:,} 次模拟校准。日常刷新只套用模型，不必再跑 100 万次。"


@app.post("/api/contracts/analyze")
async def analyze_contracts(body: AnalyzeBody) -> dict[str, Any]:
    settings = load_settings()
    interval = body.interval or settings.get("kline_interval") or "4h"
    n_sims = int(body.n_sims or settings.get("monte_carlo_sims") or 1_000_000)
    requested = (body.mode or "auto").strip().lower()
    model = await _ensure_fitted_model()
    has_model = bool(model and model.get("weights") and int(model.get("n_sims") or 0) >= 1_000_000)
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
            risk_cfg = RiskConfig.from_settings(settings)
            threshold = risk_cfg.threshold
            sl_m = risk_cfg.base_sl_mult
            tp_m = risk_cfg.base_tp_mult
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
            if kind == "fit":
                _jobs[job_id]["phase"] = "100万次权重校准"
                expect_maps = []
                names: list[str] = list(INITIAL_INDICATOR_SHARES)
                # Median across top names is enough; walking every coin's history is too slow for a global model.
                for _sym, df in list(frames.items())[:25]:
                    try:
                        emap = await asyncio.to_thread(path_expectancy, df, risk_cfg)
                        if emap:
                            expect_maps.append(emap)
                            names = list(emap.keys())
                    except Exception:
                        continue
                weights = await asyncio.to_thread(
                    fit_global_weights,
                    expect_maps,
                    names,
                    None,
                    n_sims,
                    top_pct,
                    None,
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
                _jobs[job_id]["model"] = {"n_sims": n_sims, "fitted_at": model_out["fitted_at"], "sample_count": len(expect_maps)}
            else:
                weights = (model or {}).get("weights") or {}

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
                    risk_cfg,
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

            scored = [r for r in _jobs[job_id]["results"] if not r.get("error")]
            errors = [r for r in _jobs[job_id]["results"] if r.get("error")]
            apply_portfolio_overlay(scored, risk_cfg)
            tradable_n = sum(1 for r in scored if r.get("tradable"))
            _jobs[job_id]["results"] = scored + errors
            _jobs[job_id]["tradable_count"] = tradable_n
            _jobs[job_id]["phase"] = f"可做 {tradable_n} 个（按 1R 等风险，最多 {risk_cfg.max_positions} 仓）"
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["n_sims"] = n_sims
            await db.save_analysis_run(_jobs[job_id])
        except Exception as exc:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["error"] = f"{exc}\n{traceback.format_exc()}"

    asyncio.create_task(runner())
    return {"job_id": job_id, "kind": kind, "reused": False}


@app.get("/api/contracts/analyze/{job_id}")
async def analyze_status(job_id: str) -> dict[str, Any]:
    job = _jobs.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    results = await _attach_marks("contract", job.get("results") or [])
    return {**job, "results": results}


@app.get("/api/contracts/status")
async def contracts_fit_status() -> dict[str, Any]:
    running_id, running = _running_analyze_job()
    model = await _ensure_fitted_model()
    fitted = bool(model and model.get("weights") and int(model.get("n_sims") or 0) >= 1_000_000)
    model_pub = None
    if model:
        model_pub = {k: model.get(k) for k in ("n_sims", "fitted_at", "source", "sample_count", "interval")}
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
            "results": await _attach_marks("contract", running.get("results") or []),
        }
    last = await db.latest_analysis_run()
    results = await _attach_marks("contract", (last or {}).get("results") or [])
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
        "meme",
        "meme",
        90,
        refresh,
        lambda: scan_meme_coins(
            min_liquidity_usd=float(settings.get("meme_min_liquidity_usd") or 20_000),
            min_unique_buyers=int(settings.get("meme_min_unique_buyers") or 8),
            min_holder_growth=int(settings.get("meme_min_holder_growth") or 5),
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
        "ambassadors_v2",
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
        "launches_v2",
        "launch",
        180,
        refresh,
        lambda: scan_launches(twitter_bearer=str(settings.get("twitter_bearer_token") or ""), lookback_days=7),
    )


@app.get("/api/airdrops")
async def airdrops(refresh: bool = Query(False)) -> dict[str, Any]:
    settings = load_settings()
    return await _scan_or_cache(
        "airdrops",
        "airdrop",
        3600,
        refresh,
        lambda: scan_airdrops(min_funding_usd=float(settings.get("airdrop_min_funding_usd") or 20_000_000)),
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


