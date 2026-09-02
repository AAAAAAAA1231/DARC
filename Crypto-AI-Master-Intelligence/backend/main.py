"""FastAPI application. Analysis / simulation / tracking / alerts only — no order routing."""

from __future__ import annotations

import traceback
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from backend.api.schemas import (
    AlertResolveIn,
    FillIn,
    FootballTrackIn,
    NoteIn,
    RollbackIn,
    SimulationIn,
    StatusUpdate,
)
from backend.core.config import get_settings
from backend.core.paths import frontend_dist
from backend.core.enums import ProjectStatus, RiskProfile
from backend.core.logging import get_logger, setup_logging
from backend.data_sources.registry import all_providers, bootstrap_providers
from backend.database.orm import Notification, Project
from backend.database.session import SessionLocal, get_session, init_db
from backend.schedulers.jobs import start_scheduler
from backend.services import airdrop as airdrop_svc
from backend.services import dashboard as dashboard_svc
from backend.services import football as football_svc
from backend.services import futures as futures_svc
from backend.services import holdings as holdings_svc
from backend.services import launch as launch_svc
from backend.services import lottery as lottery_svc
from backend.services import notifications as notify_svc
from backend.services import portfolio as portfolio_svc
from backend.services import projects as project_svc
from backend.services import radar as radar_svc
from backend.services import review as review_svc
from backend.services import spot as spot_svc
from backend.services.model_center import list_versions, rollback
from backend.simulations.jobs import cancel_job, create_job, pause_job, resume_job, start_job
from backend.simulations.monte_carlo import detect_gpu
from backend.database.orm import SimulationJob

setup_logging()
log = get_logger("api")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    bootstrap_providers()
    start_scheduler()
    log.info("app_started")
    yield
    log.info("app_stopped")


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(_: Request, exc: Exception) -> JSONResponse:
    log.error("unhandled_error %s", traceback.format_exc())
    return JSONResponse(status_code=500, content={"ok": False, "error": str(exc), "crash": False})


def _session():
    return next(get_session())


@app.get("/api/ready")
async def ready():
    """Local process liveness only. Does not probe vendors (those belong on /api/health)."""
    return {"ok": True, "app": settings.app_name}


@app.get("/api/health")
async def health():
    bootstrap_providers()
    statuses = {}
    for name, provider in all_providers().items():
        try:
            env = await provider.health()
            statuses[name] = {
                "status": env.status.value,
                "error": env.error,
                "data_quality": env.data_quality.value,
            }
        except Exception as exc:  # noqa: BLE001
            statuses[name] = {"status": "unknown_error", "error": str(exc)}
    return {
        "ok": True,
        "app": settings.app_name,
        "disclaimer": settings.disclaimer,
        "gpu": detect_gpu(),
        "providers": statuses,
        "auto_trading": False,
        "private_keys_allowed": False,
    }


@app.get("/api/dashboard")
async def dashboard():
    session = SessionLocal()
    try:
        result = await dashboard_svc.build(session)
        session.commit()
        return result
    finally:
        session.close()


@app.get("/api/market/klines")
async def market_klines(symbol: str = Query("BTCUSDT"), interval: str = Query("1d"), futures: bool = False, limit: int = Query(180, ge=20, le=1000)):
    from backend.data_sources.binance import BinanceProvider
    from backend.data_sources.registry import get_provider

    provider = get_provider("binance")
    assert isinstance(provider, BinanceProvider)
    env = await provider.klines(symbol, interval, limit, futures=futures)
    return {"ok": env.ok, "source_status": env.as_dict() if not env.ok else {"status": env.status.value, "n": len(env.payload or [])}, "candles": env.payload or []}


@app.get("/api/radar/latest")
async def radar_latest():
    session = SessionLocal()
    try:
        return radar_svc.latest_pool(session)
    finally:
        session.close()


@app.get("/api/futures/latest")
async def futures_latest():
    session = SessionLocal()
    try:
        return futures_svc.latest_top3(session)
    finally:
        session.close()


@app.get("/api/spot/latest")
async def spot_latest(profile: str | None = None):
    session = SessionLocal()
    try:
        return spot_svc.latest(session, profile=profile)
    finally:
        session.close()


@app.get("/api/airdrop/latest")
async def airdrop_latest():
    session = SessionLocal()
    try:
        return airdrop_svc.latest(session)
    finally:
        session.close()


@app.get("/api/launch/latest")
async def launch_latest():
    session = SessionLocal()
    try:
        return launch_svc.latest(session)
    finally:
        session.close()


@app.get("/api/football/latest")
async def football_latest():
    session = SessionLocal()
    try:
        return football_svc.latest(session)
    finally:
        session.close()


@app.get("/api/lottery/latest")
async def lottery_latest(game: str = Query("ssq")):
    session = SessionLocal()
    try:
        return lottery_svc.latest(session, game=game)
    finally:
        session.close()


@app.get("/api/btc/cycle")
async def btc_cycle(refresh: bool = False):
    from backend.services import btc_cycle as btc_svc

    session = SessionLocal()
    try:
        result = await (btc_svc.analyze(session) if refresh else btc_svc.latest_or_analyze(session))
        session.commit()
        return result
    finally:
        session.close()


@app.post("/api/radar/scan")
async def radar_scan(limit: int = Query(30, ge=5, le=80)):
    session = SessionLocal()
    try:
        result = await radar_svc.scan_radar(session, limit=limit)
        session.commit()
        return result
    finally:
        session.close()


@app.get("/api/radar/security")
async def radar_security():
    session = SessionLocal()
    try:
        return {"scans": radar_svc.latest_scans(session)}
    finally:
        session.close()


@app.post("/api/futures/scan")
async def futures_scan(analyze_n: int = Query(12, ge=3, le=40)):
    session = SessionLocal()
    try:
        result = await futures_svc.scan(session, analyze_n=analyze_n)
        session.commit()
        return result
    finally:
        session.close()


@app.post("/api/spot/scan")
async def spot_scan(profile: str = Query("BALANCED")):
    session = SessionLocal()
    try:
        result = await spot_svc.scan(session, profile=RiskProfile(profile.upper()))
        session.commit()
        return result
    finally:
        session.close()


@app.post("/api/airdrop/scan")
async def airdrop_scan():
    session = SessionLocal()
    try:
        result = await airdrop_svc.scan(session)
        session.commit()
        return result
    finally:
        session.close()


@app.post("/api/launch/scan")
async def launch_scan():
    session = SessionLocal()
    try:
        result = await launch_svc.scan(session)
        session.commit()
        return result
    finally:
        session.close()


@app.post("/api/football/refresh")
async def football_refresh():
    session = SessionLocal()
    try:
        result = await football_svc.refresh(session)
        football_svc.settle_bets(session)
        session.commit()
        return result
    finally:
        session.close()


@app.post("/api/football/track")
async def football_track(body: FootballTrackIn):
    session = SessionLocal()
    try:
        bet = football_svc.track_bet(
            session,
            body.match_external_id,
            user_placed_bet=body.user_placed_bet,
            market=body.market,
            selection=body.selection,
            stake=body.stake,
            odds=body.odds,
        )
        session.commit()
        return {"ok": True, "id": bet.id}
    finally:
        session.close()


@app.post("/api/lottery/refresh")
async def lottery_refresh(game: str = Query("ssq")):
    session = SessionLocal()
    try:
        result = await lottery_svc.refresh(session, game=game)
        session.commit()
        return result
    finally:
        session.close()


@app.get("/api/portfolio")
async def portfolio(module: str | None = None):
    session = SessionLocal()
    try:
        return await portfolio_svc.dashboard(session, module=module)
    finally:
        session.close()


@app.post("/api/portfolio/fill")
async def portfolio_fill(body: FillIn):
    session = SessionLocal()
    try:
        pos = portfolio_svc.record_fill(session, **body.model_dump())
        session.commit()
        return {"ok": True, "position_id": pos.id, "status": pos.status}
    finally:
        session.close()


@app.get("/api/portfolio/holdings/reeval")
async def holdings_reeval():
    session = SessionLocal()
    try:
        return {"positions": await holdings_svc.reevaluate_open(session)}
    finally:
        session.close()


@app.get("/api/holdings/overlay")
async def holdings_overlay():
    session = SessionLocal()
    try:
        return {"overlay": await holdings_svc.overlay_map(session)}
    finally:
        session.close()


@app.get("/api/assets/{symbol}")
async def asset_detail(symbol: str, interval: str = Query("1d"), futures: bool = False, limit: int = Query(180, ge=20, le=1000)):
    from backend.data_sources.binance import BinanceProvider
    from backend.data_sources.registry import get_provider

    pair = symbol.upper()
    if not pair.endswith("USDT"):
        pair = f"{pair}USDT"
    provider = get_provider("binance")
    assert isinstance(provider, BinanceProvider)
    env = await provider.klines(pair, interval, limit, futures=futures)
    ticker = None
    ticks = await (provider.futures_ticker_24h() if futures else provider.spot_ticker_24h())
    if ticks.ok:
        ticker = next((r for r in ticks.payload if r.get("symbol") == pair), None)
    session = SessionLocal()
    try:
        overlay = await holdings_svc.overlay_map(session)
    finally:
        session.close()
    holding = overlay.get(pair) or overlay.get(symbol.upper())
    return {
        "symbol": pair,
        "ok": env.ok,
        "source_status": {"status": env.status.value, "error": env.error, "n": len(env.payload or [])},
        "candles": env.payload or [],
        "ticker": ticker,
        "holding": holding,
    }


@app.get("/api/projects")
async def projects(include_hidden: bool = False, q: str | None = None, limit: int = 50, offset: int = 0):
    session = SessionLocal()
    try:
        query = project_svc.visible_filter(session.query(Project), include_hidden=include_hidden)
        if q:
            like = f"%{q}%"
            query = query.filter(Project.name.ilike(like) | Project.symbol.ilike(like) | Project.project_id.ilike(like))
        total = query.count()
        rows = query.order_by(Project.updated_at.desc()).offset(offset).limit(limit).all()
        return {
            "total": total,
            "items": [
                {
                    "project_id": r.project_id,
                    "name": r.name,
                    "symbol": r.symbol,
                    "status": r.status,
                    "hidden": r.hidden,
                    "last_score": float(r.last_score) if r.last_score is not None else None,
                    "last_security": r.last_security,
                    "narrative": r.narrative,
                }
                for r in rows
            ],
        }
    finally:
        session.close()


@app.get("/api/projects/{project_id}")
async def project_detail(project_id: str):
    session = SessionLocal()
    try:
        detail = project_svc.project_detail(session, project_id)
        if not detail:
            return JSONResponse(status_code=404, content={"error": "not found"})
        return detail
    finally:
        session.close()


@app.post("/api/projects/{project_id}/status")
async def project_status(project_id: str, body: StatusUpdate):
    session = SessionLocal()
    try:
        row = project_svc.set_status(session, project_id, ProjectStatus(body.status), reason=body.reason)
        session.commit()
        return {"ok": True, "status": row.status, "hidden": row.hidden}
    finally:
        session.close()


@app.post("/api/projects/{project_id}/notes")
async def project_notes(project_id: str, body: NoteIn):
    session = SessionLocal()
    try:
        note = project_svc.add_note(session, project_id, body.body)
        session.commit()
        return {"ok": True, "id": note.id}
    finally:
        session.close()


@app.post("/api/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, body: AlertResolveIn):
    session = SessionLocal()
    try:
        alert = project_svc.resolve_major_change(session, alert_id, body.resolution)
        session.commit()
        return {"ok": True, "resolution": alert.resolution}
    finally:
        session.close()


@app.get("/api/models")
async def models(module: str | None = None):
    session = SessionLocal()
    try:
        rows = list_versions(session, module)
        return {
            "versions": [
                {
                    "version": r.version,
                    "module": r.module,
                    "active": r.active,
                    "parent": r.parent_version,
                    "created_at": r.created_at.isoformat(),
                    "performance": r.performance,
                }
                for r in rows
            ]
        }
    finally:
        session.close()


@app.post("/api/models/review")
async def models_review(module: str = Query("FUTURES")):
    session = SessionLocal()
    try:
        result = review_svc.review_module(session, module)
        session.commit()
        return result
    finally:
        session.close()


@app.post("/api/models/rollback")
async def models_rollback(body: RollbackIn):
    session = SessionLocal()
    try:
        row = rollback(session, body.module, body.version)
        session.commit()
        return {"ok": True, "version": row.version}
    finally:
        session.close()


@app.post("/api/backtest/walk-forward")
async def backtest_wf(symbol: str = Query("BTCUSDT"), futures: bool = True):
    from backend.data_sources.binance import BinanceProvider
    from backend.data_sources.registry import get_provider
    from backend.backtest.engine import walk_forward
    from backend.strategies.weights import load_weights

    session = SessionLocal()
    try:
        provider = get_provider("binance")
        assert isinstance(provider, BinanceProvider)
        kl = await provider.klines(symbol, "1h", 500, futures=futures)
        if not kl.ok:
            return {"ok": False, "source_status": kl.as_dict()}
        weights = load_weights(session, "FUTURES")
        result = walk_forward(kl.payload, weights.weights)
        result["symbol"] = symbol
        result["model_version"] = weights.version
        return result
    finally:
        session.close()


@app.post("/api/simulations")
async def sim_create(body: SimulationIn):
    session = SessionLocal()
    try:
        job = create_job(session, body.kind, body.paths, body.parameters)
        session.commit()
        start_job(job.simulation_id)
        return {"ok": True, "simulation_id": job.simulation_id, "status": job.status, "paths": job.paths}
    finally:
        session.close()


@app.get("/api/simulations/{simulation_id}")
async def sim_get(simulation_id: str):
    session = SessionLocal()
    try:
        job = session.query(SimulationJob).filter(SimulationJob.simulation_id == simulation_id).one_or_none()
        if not job:
            return JSONResponse(status_code=404, content={"error": "not found"})
        return {
            "simulation_id": job.simulation_id,
            "kind": job.kind,
            "status": job.status,
            "paths": job.paths,
            "completed_paths": job.completed_paths,
            "progress": float(job.progress or 0),
            "speed": float(job.speed) if job.speed is not None else None,
            "eta_sec": float(job.eta_sec) if job.eta_sec is not None else None,
            "results": job.results,
            "confidence_interval": job.confidence_interval,
            "error": job.error,
            "disclaimer": "Simulation confidence is not live accuracy.",
        }
    finally:
        session.close()


@app.post("/api/simulations/{simulation_id}/pause")
async def sim_pause(simulation_id: str):
    pause_job(simulation_id)
    return {"ok": True}


@app.post("/api/simulations/{simulation_id}/resume")
async def sim_resume(simulation_id: str):
    resume_job(simulation_id)
    return {"ok": True}


@app.post("/api/simulations/{simulation_id}/cancel")
async def sim_cancel(simulation_id: str):
    cancel_job(simulation_id)
    return {"ok": True}


@app.get("/api/notifications")
async def notifications():
    session = SessionLocal()
    try:
        rows = session.query(Notification).order_by(Notification.created_at.desc()).limit(100).all()
        return {
            "items": [
                {
                    "id": n.id,
                    "kind": n.kind,
                    "title": n.title,
                    "body": n.body,
                    "read": n.read,
                    "channel": n.channel,
                    "at": n.created_at.isoformat(),
                }
                for n in rows
            ]
        }
    finally:
        session.close()


@app.post("/api/notifications/{nid}/read")
async def notification_read(nid: int):
    session = SessionLocal()
    try:
        row = session.query(Notification).filter(Notification.id == nid).one()
        row.read = True
        session.commit()
        return {"ok": True}
    finally:
        session.close()


@app.get("/api/settings")
async def api_settings():
    s = get_settings()
    return {
        "host": s.host,
        "port": s.port,
        "database_url": "sqlite" if s.database_url.startswith("sqlite") else "configured",
        "keys_present": {
            "binance": bool(s.binance_api_key),
            "coingecko": bool(s.coingecko_api_key),
            "goplus": bool(s.goplus_app_key),
            "github": bool(s.github_token),
            "football_data": bool(s.football_data_api_key),
            "telegram": bool(s.telegram_bot_token),
            "smtp": bool(s.smtp_host),
        },
        "gpu": detect_gpu(),
        "disclaimer": s.disclaimer,
        "auto_trading": False,
    }


frontend_dir = frontend_dist()


@app.get("/{full_path:path}")
async def serve_ui(full_path: str):
    """SPA fallback so /lottery and /assets/BTCUSDT load the React shell instead of JSON 404."""
    if full_path.startswith("api/") or full_path.startswith("api"):
        return JSONResponse(status_code=404, content={"ok": False, "error": "not found"})
    if frontend_dir.exists():
        candidate = frontend_dir / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        index = frontend_dir / "index.html"
        if index.is_file():
            return FileResponse(index)
    return JSONResponse(status_code=404, content={"ok": False, "error": "frontend dist missing — run npm run build"})
