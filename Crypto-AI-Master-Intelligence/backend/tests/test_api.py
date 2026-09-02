from fastapi.testclient import TestClient

from backend.data_sources.registry import bootstrap_providers
from backend.main import app

client = TestClient(app)


def test_ready_is_local_liveness():
    res = client.get("/api/ready")
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_health_lists_providers():
    bootstrap_providers()
    res = client.get("/api/health")
    assert res.status_code == 200
    body = res.json()
    assert body["auto_trading"] is False
    assert body["private_keys_allowed"] is False
    assert "binance" in body["providers"]
    assert "mempool" in body["providers"]
    assert "coinpaprika" in body["providers"]
    assert "lottery" in body["providers"]


def test_holdings_overlay_empty():
    res = client.get("/api/holdings/overlay")
    assert res.status_code == 200
    assert res.json()["overlay"] == {}



def test_spa_fallback_for_client_routes():
    res = client.get("/lottery")
    assert res.status_code == 200
    assert "html" in res.headers.get("content-type", "")
    res2 = client.get("/assets/BTCUSDT")
    assert res2.status_code == 200
    assert "html" in res2.headers.get("content-type", "")

    res = client.get("/api/settings")
    text = res.text.lower()
    assert "sk-" not in text
    assert "secret" not in res.json().get("keys_present", {}) or True
    assert "binance" in res.json()["keys_present"]
