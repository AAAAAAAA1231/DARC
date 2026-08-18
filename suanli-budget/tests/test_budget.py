from fastapi.testclient import TestClient

from suanli_budget.api import app
from suanli_budget.engine.calc import compile_budget
from suanli_budget.engine.export import export_docx, export_excel

client = TestClient(app)


def test_health_and_ui():
    h = client.get("/api/health")
    assert h.json()["ok"] is True
    page = client.get("/")
    assert page.status_code == 200
    assert "算力" in page.text
    cat = client.get("/api/catalog")
    assert cat.json()["gpus"]


def test_pflops_rounds_to_full_nodes(tmp_path):
    out = compile_budget(
        {
            "project": "测试",
            "mode": "pflops",
            "target_pflops": 10,
            "gpu_id": "h20-141",
            "cooling": "liquid",
        }
    )
    assert out["scale"]["gpu_buy"] % 8 == 0
    assert out["scale"]["nodes"] >= 1
    assert out["totals"]["total"] > 1_000_000
    assert out["totals"]["per_gpu"] > 0
    x = export_excel(out, tmp_path / "a.xlsx")
    w = export_docx(out, tmp_path / "a.docx")
    assert x.stat().st_size > 1000
    assert w.stat().st_size > 1000


def test_count_mode_and_api():
    out = compile_budget({"mode": "count", "gpu_count": 64, "gpu_id": "910b", "cooling": "air"})
    assert out["scale"]["gpu_buy"] == 64
    assert out["scale"]["nodes"] == 8
    r = client.post("/api/budget", json={"mode": "count", "gpu_count": 8, "gpu_id": "h20-141"})
    assert r.status_code == 200
    assert r.json()["scale"]["nodes"] == 1
    xls = client.get("/api/budget/excel")
    assert xls.status_code == 200
