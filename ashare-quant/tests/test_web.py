from pathlib import Path

from fastapi.testclient import TestClient

from ashare_quant.config import load_config
from ashare_quant.web.app import create_app


def test_dashboard_renders_signal_sheet():
    out = Path(__file__).resolve().parents[1] / "output"
    app = create_app(load_config(), output_dir=out)
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    page = client.get("/")
    assert page.status_code == 200
    body = page.text
    assert "量化交易辅助系统" in body
    assert "Walk-Forward" in body
    assert "置信区间" in body
    if (out / "snapshot.json").exists():
        assert "非实盘" in body
    ideas = client.get("/api/ideas").json()["ideas"]
    if ideas:
        assert all(len(str(r["symbol"])) == 6 for r in ideas)
        assert any(r.get("stop_loss") not in (None, "") for r in ideas)
        assert any(r.get("ci_p10") not in (None, "") for r in ideas)
        assert any(r.get("execute_date") for r in ideas)
