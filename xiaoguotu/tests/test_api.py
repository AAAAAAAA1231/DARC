from fastapi.testclient import TestClient

from xiaoguotu.api import app

client = TestClient(app)


def test_health_and_index():
    h = client.get("/api/health").json()
    assert h["ok"] and h["app"] == "效果图生成器"
    r = client.get("/")
    assert r.status_code == 200
    assert "效果图" in r.text


def test_scene_api_and_sheet():
    r = client.post("/api/scene", json={"mode": "aerial", "building_type": "酒店", "floors": 22})
    assert r.status_code == 200, r.text
    scene = r.json()["scene"]
    assert scene["mode"]["id"] == "aerial"
    assert scene["building"]["floors"] == 22
    sheet = client.get("/api/download/max-sheet")
    assert sheet.status_code == 200
    assert "VRaySun" in sheet.text
    assert "Physical Camera" in sheet.text
