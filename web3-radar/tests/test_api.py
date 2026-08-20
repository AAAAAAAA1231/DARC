from __future__ import annotations

from fastapi.testclient import TestClient

from web3_radar.api import app


client = TestClient(app)


def test_health_and_index():
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["ok"] is True
    assert h.json()["app"] == "链上雷达"
    page = client.get("/")
    assert page.status_code == 200
    assert "链上雷达" in page.text
    assert "接口令牌" in page.text
    assert "cz_binance" in page.text
    assert "$1M" in page.text or "$1,000,000" in page.text or "池子 ≥ $1M" in page.text


def test_settings_and_marks_roundtrip():
    s = client.get("/api/settings")
    assert s.status_code == 200
    assert s.json()["monte_carlo_sims"] == 1_000_000
    assert s.json()["meme_min_liquidity_usd"] == 1_000_000
    assert s.json()["airdrop_btc_min_funding_usd"] == 5_000_000
    marked = client.post(
        "/api/marks",
        json={"category": "ambassador", "item_key": "demo-1", "status": "applied", "note": "test"},
    )
    assert marked.status_code == 200
    listed = client.get("/api/marks", params={"category": "ambassador"})
    keys = [m["item_key"] for m in listed.json()]
    assert "demo-1" in keys


def test_wallet_participate_queue():
    from web3_radar.fallback import load_fallback, merge_items
    data = load_fallback()
    assert data["ambassadors"]
    assert data["airdrops"]
    assert all(any(str(c).lower() in {"ethereum", "bitcoin", "base", "arbitrum"} or "eth" in str(c).lower() or "bitcoin" in str(c).lower() for c in (x.get("chains") or [])) for x in data["airdrops"])
    assert data["launches"]
    assert all((x.get("chain") or "") in {"Solana", "BSC", "Solana + BSC"} for x in data["launches"])
    merged = merge_items([], data["airdrops"])
    assert len(merged) == len(data["airdrops"])
    r = client.post(
        "/api/wallet/participate",
        json={"category": "airdrop", "item": {"key": "demo", "name": "Demo", "url": "https://example.com"}, "auto": False},
    )
    assert r.status_code == 200
    assert r.json()["status"] == "pending"
    w = client.get("/api/wallet")
    assert w.status_code == 200
    assert any(t["item_key"] == "demo" for t in w.json()["tasks"])


def test_modules_return_catalog():
    a = client.get("/api/ambassadors")
    assert a.status_code == 200
    body = a.json()
    assert body["items"]
    assert not any("OKX" in str(x.get("project") or x.get("name") or "") and x.get("source") == "观察池" for x in body["items"])
    d = client.get("/api/airdrops")
    assert d.status_code == 200
    assert d.json()["items"]
    assert any(x.get("ecosystem") in {"bitcoin", "ethereum", "btc-eth"} for x in d.json()["items"])
    l = client.get("/api/launches")
    assert l.status_code == 200
    assert int(l.json().get("onchain_count") or 0) == 0
    for x in l.json().get("items") or []:
        assert x.get("verified_follow") is True, x.get("name")
        assert x.get("followed_by"), x.get("name")
        assert x.get("watch_kind") != "onchain_pool"
        assert int(x.get("official_follow_count") or 0) >= 1
        chain = str(x.get("chain") or "")
        names = set(x.get("followed_by") or [])
        if "BSC" in chain:
            assert names & {"cz_binance", "heyibinance"}
        if chain == "Solana":
            assert names & {"solana", "toly", "aeyakovenko"}
    added = client.post("/api/ambassadors", json={"project": "测试项目", "url": "https://example.com"})
    assert added.status_code == 200
    assert added.json()["source"] == "手动"
