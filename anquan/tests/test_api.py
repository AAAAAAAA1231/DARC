from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from anquan.api import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("anquan.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("anquan.store.DATA_DIR", tmp_path)
    return TestClient(app)


def test_health_catalog_export(client: TestClient):
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["port"] == 8795
    cat = client.get("/api/catalog").json()
    assert cat["hazards"]
    ws = client.get("/api/workspace").json()
    pid = ws["active_id"]
    xlsx = client.get(f"/api/projects/{pid}/export.xlsx")
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"


def test_hazard_loop_and_inspect(client: TestClient):
    ws = client.get("/api/workspace").json()
    pid = ws["active_id"]
    created = client.post(
        f"/api/projects/{pid}/hazards",
        json={"template_id": "pit", "location": "南侧基坑", "owner": "土方班", "deadline": "2026-08-19"},
    ).json()
    proj = next(p for p in created["projects"] if p["id"] == pid)
    item = next(i for i in proj["hazards"] if i.get("template_id") == "pit")
    assert item["severity"] == "重大隐患"
    stepped = client.post(
        f"/api/projects/{pid}/hazards/{item['id']}/status",
        json={"status": "待复查", "rectify_desc": "已恢复临边防护"},
    ).json()
    same = next(i for p in stepped["projects"] if p["id"] == pid for i in p["hazards"] if i["id"] == item["id"])
    assert same["status"] == "待复查"
    logged = client.post(
        f"/api/projects/{pid}/inspections",
        json={"kind": "危大工程巡视", "area": "基坑", "findings": "防护已恢复", "result": "合格"},
    ).json()
    proj = next(p for p in logged["projects"] if p["id"] == pid)
    assert proj["inspections"][0]["findings"] == "防护已恢复"
