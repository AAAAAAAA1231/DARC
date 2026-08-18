from fastapi.testclient import TestClient

from jishubiao.api import app


def test_health_and_generate():
    client = TestClient(app)
    assert client.get("/api/health").json()["ok"] is True
    cat = client.get("/api/catalog").json()
    assert cat["specialties"]
    res = client.post("/api/generate", json={"name": "接口试验工程", "specialty": "房屋建筑", "structure": "剪力墙", "residential": False})
    data = res.json()
    assert res.status_code == 200
    assert data["chapters"]
    assert data["codes"]
    dl = client.get("/api/download/docx")
    assert dl.status_code == 200
    assert dl.headers["content-type"].startswith("application/")
