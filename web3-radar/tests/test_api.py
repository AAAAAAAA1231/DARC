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
    assert "单边快讯" in page.text
    assert "只看高影响提醒" in page.text
    assert "只看推荐" in page.text
    assert "成功率" not in page.text
    assert "套用已拟合模型" not in page.text
    assert "10亿次" not in page.text
    assert "综合分" not in page.text
    assert "分析此币" in page.text
    assert "名人喊单" in page.text
    assert "24 小时" in page.text
    assert "@solana" in page.text
    assert "@toly" in page.text
    assert "近一个月" in page.text
    assert "只要项目" in page.text
    assert "不要人物" in page.text
    assert "token launch" in page.text
    assert "自动打新盯盘" in page.text
    assert "发币 ≤ 3 天" in page.text
    assert "24h 提及" in page.text
    assert "近一周 KOL" in page.text
    assert "不会索取助记词或私钥" in page.text
    assert "行业名人" not in page.text
    assert '<span class="pill">CZ</span>' not in page.text
    assert 'id="s_private_key"' not in page.text
    assert "private_key" not in page.text
    js = client.get("/static/js/app.js")
    assert js.status_code == 200
    assert "行业名人" not in js.text
    assert "只要项目" in js.text
    assert "最近一个月" in js.text
    assert "private_key" not in js.text
    assert "$1M" in page.text or "$1,000,000" in page.text or "池子 ≥ $1M" in page.text


def test_settings_and_marks_roundtrip():
    s = client.get("/api/settings")
    assert s.status_code == 200
    assert s.json()["monte_carlo_sims"] == 1_000_000_000
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
    assert data["news"]
    assert all((x.get("chain") or "") == "Solana" for x in data["launches"])
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
        assert x.get("watch_kind") != "onchain_pool"
        kind = x.get("source_kind") or x.get("watch_kind") or ""
        if kind in {"search", "watch"} or x.get("watch_kind") in {"search", "manual_watch"}:
            continue
        assert x.get("verified_follow") is True, x.get("name")
        assert x.get("followed_by"), x.get("name")
        names = set(x.get("followed_by") or [])
        assert names <= {"solana", "toly"}
        assert names
        assert int(x.get("official_follow_count") or 0) >= 1
        assert x.get("follow_tier") == "official"
        assert x.get("token_status") == "未发币"
        assert str(x.get("chain") or "") == "Solana"
    n = client.get("/api/news")
    assert n.status_code == 200
    news_body = n.json()
    for item in news_body.get("items") or []:
        secs = item.get("seconds_to")
        if secs is not None:
            assert abs(int(secs)) <= 24 * 3600, item.get("title")
    if news_body.get("items"):
        assert news_body.get("stance", {}).get("stance") in {"做多", "做空", "观望"}
        assert "groups" in (news_body.get("stance") or {})
    assert all(x.get("title") and x.get("category") and x.get("bias") in {"偏多", "偏空", "方向未定"} for x in news_body["items"])
    added = client.post("/api/ambassadors", json={"project": "测试项目", "url": "https://example.com"})
    assert added.status_code == 200
    assert added.json()["source"] == "手动"


def test_settings_reject_private_key():
    r = client.post("/api/settings", json={"settings": {"private_key": "0xabc"}})
    assert r.status_code == 400
    r2 = client.post("/api/settings", json={"settings": {"mnemonic": "alpha beta"}})
    assert r2.status_code == 400
    ok = client.post("/api/launch-watches", json={"handle": "helixsvm"})
    assert ok.status_code == 200
    assert ok.json()["handle"] == "helixsvm"
    bad = client.post("/api/launch-watches", json={"handle": "not a handle!!!"})
    assert bad.status_code == 400
    gone = client.post("/api/launch-watches/remove", json={"handle": "helixsvm"})
    assert gone.status_code == 200


def test_mac_frozen_writes_to_application_support(monkeypatch):
    from web3_radar import config

    monkeypatch.setattr(config.sys, "platform", "darwin")
    monkeypatch.setattr(config.sys, "frozen", True, raising=False)
    root = config._writable_root()
    assert root.name == "ChainRadar"
    assert "Application Support" in str(root)


def test_windows_packaging_is_signed_style_exe():
    from pathlib import Path

    spec = Path("ChainRadar.spec").read_text(encoding="utf-8")
    assert "COLLECT(" not in spec
    assert "exclude_binaries=True" not in spec
    assert "upx=False" in spec
    assert 'version="version_info.txt"' in spec
    assert "chainradar.ico" in spec
    assert "BUNDLE(" in spec
    ico = Path("web3_radar/resources/chainradar.ico")
    assert ico.is_file() and ico.stat().st_size > 100
    ver = Path("version_info.txt").read_text(encoding="utf-8")
    assert "链上雷达" in ver
    assert "FileDescription" in ver
    workflow = Path(__file__).resolve().parents[2] / ".github/workflows/build-web3-radar.yml"
    text = workflow.read_text(encoding="utf-8")
    assert "macos-latest" in text
    assert "macos-15-intel" in text
    assert "ChainRadar-mac.zip" in text
    assert "ChainRadar-mac-intel.zip" in text
    assert "ChainRadar.exe" in text
    assert "hdiutil" not in text
