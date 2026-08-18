from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhiliang.api import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr("zhiliang.config.DATA_DIR", tmp_path)
    monkeypatch.setattr("zhiliang.store.DATA_DIR", tmp_path)
    return TestClient(app)


def test_health_catalog_export(client: TestClient):
    health = client.get("/api/health").json()
    assert health["ok"] is True
    assert health["port"] == 8794
    cat = client.get("/api/catalog").json()
    assert cat["defects"]
    ws = client.get("/api/workspace").json()
    assert ws["projects"]
    pid = ws["active_id"]
    xlsx = client.get(f"/api/projects/{pid}/export.xlsx")
    assert xlsx.status_code == 200
    assert xlsx.content[:2] == b"PK"


def test_issue_loop_and_inspect(client: TestClient):
    ws = client.get("/api/workspace").json()
    pid = ws["active_id"]
    created = client.post(
        f"/api/projects/{pid}/issues",
        json={"defect_id": "axis", "location": "1层轴线", "owner": "测量员", "deadline": "2026-09-01"},
    ).json()
    proj = next(p for p in created["projects"] if p["id"] == pid)
    issue = next(i for i in proj["issues"] if i.get("defect_id") == "axis")
    stepped = client.post(
        f"/api/projects/{pid}/issues/{issue['id']}/status",
        json={"status": "待复查", "rectify_desc": "已校正"},
    ).json()
    same = next(i for p in stepped["projects"] if p["id"] == pid for i in p["issues"] if i["id"] == issue["id"])
    assert same["status"] == "待复查"
    logged = client.post(
        f"/api/projects/{pid}/inspections",
        json={"kind": "旁站", "area": "1层", "findings": "轴线已纠偏", "result": "合格"},
    ).json()
    proj = next(p for p in logged["projects"] if p["id"] == pid)
    assert proj["inspections"][0]["findings"] == "轴线已纠偏"
