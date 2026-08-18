from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from jindu.api import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("jindu.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("jindu.store.DATA_DIR", tmp_path)
    return TestClient(app)


def test_health_workspace_and_exports(client: TestClient):
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["port"] == 8793
    tpl = client.get("/api/templates").json()
    assert len(tpl["templates"]) >= 4
    ws = client.get("/api/workspace").json()
    assert ws["projects"]
    pid = ws["active_id"]
    xlsx = client.get(f"/api/projects/{pid}/export.xlsx")
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"
    png = client.get(f"/api/projects/{pid}/export.png")
    assert png.status_code == 200
    assert png.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_template_log_task_and_save(client: TestClient):
    client.get("/api/workspace")
    created = client.post(
        "/api/projects/from-template",
        json={"template_id": "装饰装修", "name": "办公楼精装", "contract_start": "2026-04-01"},
    ).json()
    proj = next(p for p in created["projects"] if p["name"] == "办公楼精装")
    logged = client.post(
        f"/api/projects/{proj['id']}/logs",
        json={"date": "2026-04-02", "weather": "晴", "work": "完成进场准备", "manpower": "12"},
    ).json()
    same = next(p for p in logged["projects"] if p["id"] == proj["id"])
    assert same["logs"][0]["work"] == "完成进场准备"
    added = client.post(f"/api/projects/{proj['id']}/tasks", json={"name": "样板间", "duration": 9}).json()
    same = next(p for p in added["projects"] if p["id"] == proj["id"])
    assert any(t["name"] == "样板间" for t in same["tasks"])
    saved = client.put("/api/workspace", json=added).json()
    assert saved["projects"]
