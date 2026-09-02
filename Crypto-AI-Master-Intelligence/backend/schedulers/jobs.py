"""Hourly/daily jobs. Failures are logged; they never crash the desktop process."""

from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.database.session import SessionLocal

logger = get_logger("scheduler")
_scheduler: BackgroundScheduler | None = None


def _run(job_name: str, coro_factory) -> None:  # noqa: ANN001
    import asyncio

    session = SessionLocal()
    try:
        asyncio.run(coro_factory(session))
        session.commit()
        logger.info("scheduled_job_ok name=%s", job_name)
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        logger.error("scheduled_job_failed name=%s err=%s", job_name, exc)
    finally:
        session.close()


async def _btc(session) -> None:  # noqa: ANN001
    from backend.services.btc_cycle import analyze

    await analyze(session)


async def _football(session) -> None:  # noqa: ANN001
    from backend.services.football import refresh, settle_bets

    await refresh(session)
    settle_bets(session)


async def _review(session) -> None:  # noqa: ANN001
    from backend.services.review import review_module

    for module in ("FUTURES", "SPOT", "FOOTBALL", "RADAR"):
        review_module(session, module)


def start_scheduler() -> None:
    global _scheduler
    settings = get_settings()
    if not settings.scheduler_enabled:
        logger.info("scheduler_disabled")
        return
    if _scheduler:
        return
    _scheduler = BackgroundScheduler()
    _scheduler.add_job(lambda: _run("btc_cycle", _btc), "interval", hours=1, id="hourly_btc")
    _scheduler.add_job(lambda: _run("football", _football), "cron", hour=6, id="daily_football")
    _scheduler.add_job(lambda: _run("review", _review), "cron", hour=7, id="daily_review")
    _scheduler.start()
    logger.info("scheduler_started")
