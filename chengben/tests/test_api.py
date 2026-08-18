from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chengben.api import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("chengben.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("chengben.store.DATA_DIR", tmp_path)
    return TestClient(app)


def test_health_and_export(client: TestClient):
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["port"] == 8795
    cat = client.get("/api/catalog").json()
    assert len(cat["templates"]) >= 3
    ws = client.get("/api/workspace").json()
    pid = ws["active_id"]
    xlsx = client.get(f"/api/projects/{pid}/export.xlsx")
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"


def test_template_log_corr(client: TestClient):
    client.get("/api/workspace")
    created = client.post(
        "/api/projects/from-template",
        json={"template_id": "市政道路", "name": "试验路", "cost_lead": "成本员"},
    ).json()
    proj = next(p for p in created["projects"] if p["name"] == "试验路")
    item = proj["items"][0]
    logged = client.post(
        f"/api/projects/{proj['id']}/logs",
        json={"item_id": item["id"], "kind": "材料进场", "amount": 20000, "qty": 2},
    ).json()
    same = next(p for p in logged["projects"] if p["id"] == proj["id"])
    hit = next(i for i in same["items"] if i["id"] == item["id"])
    assert hit["actual_amount"] >= 20000
    corr = client.post(
        f"/api/projects/{proj['id']}/corrections",
        json={"item_id": item["id"], "title": "压价", "kind": "价差", "deviation_amount": 8000, "action": "重新询价"},
    ).json()
    same = next(p for p in corr["projects"] if p["id"] == proj["id"])
    assert same["corrections"][0]["title"] == "压价"
    cid = same["corrections"][0]["id"]
    closed = client.post(
        f"/api/projects/{proj['id']}/corrections/{cid}/status",
        json={"status": "已闭合"},
    ).json()
    same = next(p for p in closed["projects"] if p["id"] == proj["id"])
    assert same["corrections"][0]["status"] == "已闭合"
