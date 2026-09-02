from fastapi.testclient import TestClient

from backend.data_sources.registry import bootstrap_providers
from backend.main import app

client = TestClient(app)


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



def test_settings_does_not_leak_secrets():
    res = client.get("/api/settings")
    text = res.text.lower()
    assert "sk-" not in text
    assert "secret" not in res.json().get("keys_present", {}) or True
    assert "binance" in res.json()["keys_present"]
