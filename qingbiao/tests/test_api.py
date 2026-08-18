from fastapi.testclient import TestClient

from qingbiao.api import app
from qingbiao.store import store

client = TestClient(app)


def setup_function() -> None:
    store.reset()


def test_health_and_home():
    h = client.get("/api/health")
    assert h.status_code == 200
    assert h.json()["offline"] is True
    page = client.get("/")
    assert page.status_code == 200
    assert "经济标" in page.text
    assert "技术标" in page.text
    css = client.get("/static/css/app.css")
    assert css.status_code == 200


def test_analyze_requires_three_bidders():
    r = client.post("/api/economic/analyze")
    assert r.status_code == 400
    t = client.post("/api/technical/analyze")
    assert t.status_code == 400
    p = client.post("/api/project", json={"name": "x", "floors": "2", "area": "100", "structure": "框架"})
    assert p.status_code == 200
