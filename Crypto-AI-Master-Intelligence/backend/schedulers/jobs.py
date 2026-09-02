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


async def _radar(session) -> None:  # noqa: ANN001
    from backend.services.radar import scan_radar

    await scan_radar(session, limit=12)


async def _airdrop(session) -> None:  # noqa: ANN001
    from backend.services.airdrop import scan

    await scan(session, limit=20)


async def _launch(session) -> None:  # noqa: ANN001
    from backend.services.launch import scan

    await scan(session)


async def _lottery(session) -> None:  # noqa: ANN001
    from backend.services.lottery import refresh

    await refresh(session, game="ssq")


async def _portfolio(session) -> None:  # noqa: ANN001
    from backend.services.portfolio import dashboard

    await dashboard(session)


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
    _scheduler.add_job(lambda: _run("portfolio", _portfolio), "interval", hours=1, id="hourly_portfolio")
    _scheduler.add_job(lambda: _run("radar", _radar), "cron", hour=1, id="daily_radar")
    _scheduler.add_job(lambda: _run("airdrop", _airdrop), "cron", hour=2, id="daily_airdrop")
    _scheduler.add_job(lambda: _run("launch", _launch), "cron", hour=3, id="daily_launch")
    _scheduler.add_job(lambda: _run("lottery", _lottery), "cron", hour=5, id="daily_lottery")
    _scheduler.add_job(lambda: _run("football", _football), "cron", hour=6, id="daily_football")
    _scheduler.add_job(lambda: _run("review", _review), "cron", hour=7, id="daily_review")
    _scheduler.start()
    logger.info("scheduler_started")
