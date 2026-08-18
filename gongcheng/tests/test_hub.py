from fastapi.testclient import TestClient

from hub.api import app

PREFIXES = ("/qingbiao", "/anquan", "/jindu", "/zhiliang", "/chengben", "/jishubiao")


def test_home_and_all_modules():
    client = TestClient(app)
    home = client.get("/")
    assert home.status_code == 200
    assert "工程工作台" in home.text
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["port"] == 8788
    assert len(health["modules"]) == 6
    for prefix in PREFIXES:
        r = client.get(prefix + "/api/health")
        assert r.status_code == 200, prefix
        assert r.json()["ok"] is True
        page = client.get(prefix + "/")
        assert page.status_code == 200, prefix
        assert "工程工作台" in page.text
