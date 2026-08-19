from fastapi.testclient import TestClient

from shigongtu.api import app


client = TestClient(app)


def test_health_and_presets():
    h = client.get("/api/health").json()
    assert h["ok"] is True
    p = client.get("/api/presets").json()
    assert "办公楼" in p["building_types"]
    assert "框架" in p["structures"]


def test_index_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "施工图" in r.text


def test_generate_api(tmp_path, monkeypatch):
    r = client.post(
        "/api/generate",
        json={"name": "接口试验楼", "building_type": "学校", "floors": 3, "floor_area": 900, "basement": 0},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] and data["count"] >= 20
    first = data["drawings"][0]
    svg = client.get(f"/api/drawing/{first['id']}/svg")
    assert svg.status_code == 200
    assert b"<svg" in svg.content
    z = client.get("/api/download/zip")
    assert z.status_code == 200
    assert z.headers["content-type"].startswith("application/zip") or z.content[:2] == b"PK"
