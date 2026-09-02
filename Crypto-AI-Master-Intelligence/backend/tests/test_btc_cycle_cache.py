from backend.database.orm import BtcCycleHistory
from backend.database.session import SessionLocal
from backend.services.btc_cycle import latest_or_analyze


async def test_latest_or_analyze_uses_fresh_snapshot():
    session = SessionLocal()
    try:
        session.add(
            BtcCycleHistory(
                snapshot={
                    "ok": True,
                    "regime": "BULL",
                    "phase": "EXPANSION",
                    "klines": [{"open": "1"}],
                    "disclaimer": "cached fixture",
                }
            )
        )
        session.commit()
        out = await latest_or_analyze(session, max_age_minutes=90)
        assert out["cached"] is True
        assert "klines" not in out
        assert out["regime"] == "BULL"
    finally:
        session.close()
