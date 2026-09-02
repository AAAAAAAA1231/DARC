"""Background simulation jobs: start/pause/resume/cancel/progress/ETA. Never blocks the API event loop."""

from __future__ import annotations

import threading
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.enums import SimulationStatus
from backend.core.logging import get_logger
from backend.core.parsing import utcnow
from backend.database.orm import SimulationJob, SimulationResult
from backend.database.session import SessionLocal
from backend.simulations.monte_carlo import gbm_terminal_prices, lottery_coverage_sim

logger = get_logger("sim_jobs")

_LOCK = threading.Lock()
_CONTROL: dict[str, str] = {}
_THREADS: dict[str, threading.Thread] = {}


def create_job(session: Session, kind: str, paths: int, parameters: dict[str, Any], model_version: str | None = None) -> SimulationJob:
    settings = get_settings()
    paths = min(max(paths, 1), settings.max_paths)
    sim_id = str(uuid.uuid4())
    job = SimulationJob(
        simulation_id=sim_id,
        kind=kind,
        status=SimulationStatus.QUEUED.value,
        paths=paths,
        parameters=parameters,
        model_version=model_version,
        dataset=parameters.get("dataset"),
        strategy_weights=parameters.get("weights"),
    )
    session.add(job)
    session.flush()
    return job


def start_job(simulation_id: str) -> None:
    with _LOCK:
        _CONTROL[simulation_id] = "run"
        t = threading.Thread(target=_run, args=(simulation_id,), daemon=True, name=f"sim-{simulation_id[:8]}")
        _THREADS[simulation_id] = t
        t.start()


def pause_job(simulation_id: str) -> None:
    _CONTROL[simulation_id] = "pause"


def resume_job(simulation_id: str) -> None:
    _CONTROL[simulation_id] = "run"


def cancel_job(simulation_id: str) -> None:
    _CONTROL[simulation_id] = "cancel"


def _wait_if_paused(simulation_id: str) -> bool:
    while _CONTROL.get(simulation_id) == "pause":
        time.sleep(0.2)
    return _CONTROL.get(simulation_id) != "cancel"


def _run(simulation_id: str) -> None:
    session = SessionLocal()
    try:
        job = session.query(SimulationJob).filter(SimulationJob.simulation_id == simulation_id).one()
        job.status = SimulationStatus.RUNNING.value
        job.started_at = utcnow()
        session.commit()
        settings = get_settings()
        chunk = settings.chunk_size
        kind = job.kind
        t0 = time.time()
        if kind == "gbm":
            params = job.parameters or {}
            result = gbm_terminal_prices(
                float(params.get("spot", 1.0)),
                float(params.get("mu", 0.0)),
                float(params.get("sigma", 0.5)),
                float(params.get("dt", 1.0)),
                int(job.paths),
                seed=int(params.get("seed", 7)),
                chunk=chunk,
            )
            job.completed_paths = job.paths
            job.progress = 1
            job.results = result
            job.confidence_interval = result.get("quantiles")
        elif kind == "lottery":
            from backend.database.orm import LotteryResult

            game = (job.parameters or {}).get("game", "ssq")
            draws = session.query(LotteryResult).filter(LotteryResult.game == game).all()
            historical = [d.numbers for d in draws]
            result = lottery_coverage_sim(game, historical, int(job.paths), chunk=chunk)
            job.completed_paths = job.paths
            job.progress = 1
            job.results = result
            job.confidence_interval = result.get("ci")
        else:
            raise ValueError(f"unknown simulation kind {kind}")
        if not _wait_if_paused(simulation_id):
            job.status = SimulationStatus.CANCELLED.value
        else:
            job.status = SimulationStatus.COMPLETED.value
        elapsed = max(time.time() - t0, 1e-6)
        job.speed = job.paths / elapsed
        job.eta_sec = 0
        job.ended_at = utcnow()
        session.add(SimulationResult(simulation_id=simulation_id, chunk_index=0, payload=job.results or {}))
        session.commit()
        logger.info("simulation_done id=%s kind=%s paths=%s", simulation_id, kind, job.paths)
    except Exception as exc:  # noqa: BLE001
        logger.error("simulation_failed id=%s err=%s", simulation_id, exc)
        session.rollback()
        job = session.query(SimulationJob).filter(SimulationJob.simulation_id == simulation_id).one_or_none()
        if job:
            job.status = SimulationStatus.FAILED.value
            job.error = str(exc)
            job.ended_at = utcnow()
            session.commit()
    finally:
        session.close()
