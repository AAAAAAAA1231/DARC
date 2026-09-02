from backend.data_sources.registry import bootstrap_providers
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_latest_module_endpoints_empty_or_cached():
    bootstrap_providers()
    for path in (
        "/api/radar/latest",
        "/api/futures/latest",
        "/api/spot/latest",
        "/api/airdrop/latest",
        "/api/launch/latest",
        "/api/football/latest",
        "/api/lottery/latest?game=ssq",
    ):
        res = client.get(path)
        assert res.status_code == 200, path
        body = res.json()
        assert "disclaimer" in body or "items" in body or "draws" in body or "projects" in body or "top3" in body or "predictions" in body or "recommended" in body
        # Empty cache is valid. Fabricated rows are not.
        if "projects" in body:
            assert isinstance(body["projects"], list)
        if "draws" in body:
            assert isinstance(body["draws"], list)


def test_btc_cycle_uses_inserted_snapshot():
    from backend.database.orm import BtcCycleHistory
    from backend.database.session import SessionLocal

    session = SessionLocal()
    try:
        session.add(
            BtcCycleHistory(
                snapshot={
                    "ok": True,
                    "regime": "BULL",
                    "missing_indicators": {"mvrv": "UNKNOWN — no on-chain provider configured"},
                }
            )
        )
        session.commit()
    finally:
        session.close()
    res = client.get("/api/btc/cycle")
    assert res.status_code == 200
    body = res.json()
    assert body.get("regime") == "BULL"
    assert body.get("cached") is True
    assert "UNKNOWN" in str(body.get("missing_indicators", {}).get("mvrv", "UNKNOWN"))
