from pathlib import Path

from ashare_quant.desktop import load_idea_rows, port_is_open, wait_for_listen
from ashare_quant.panel_html import write_panel_html
from ashare_quant.paths import resolve_config_path
from ashare_quant.pipeline import run_pipeline


def test_bundled_config_resolves():
    path = resolve_config_path()
    assert path.exists()
    assert path.name.endswith(".yaml")


def test_load_idea_rows_pads_szse_codes(tmp_path):
    csv = tmp_path / "ideas.csv"
    csv.write_text("symbol,name,action,shares\n2005,测试,buy,100\n688001,科创,buy,200\n", encoding="utf-8")
    rows = load_idea_rows(csv)
    assert rows[0]["symbol"] == "002005"
    assert rows[1]["symbol"] == "688001"


def test_quick_pipeline_writes_ideas(tiny_cfg, tiny_market, tmp_path):
    bars, meta = tiny_market
    from ashare_quant.data.provider import MarketData

    data = tmp_path / "bars.csv"
    MarketData(bars, meta).save(data)
    out = tmp_path / "out"
    result = run_pipeline(tiny_cfg, output_dir=out, data_path=data, mode="quick")
    assert (out / "ideas.csv").exists()
    assert (out / "snapshot.json").exists()
    assert result.extra["snapshot"].get("mode") == "quick"
    assert len(result.ideas) >= 1


def test_port_is_open_detects_listener():
    import socket

    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    port = srv.getsockname()[1]
    try:
        assert port_is_open("127.0.0.1", port)
        assert wait_for_listen("127.0.0.1", port, seconds=1.0)
    finally:
        srv.close()
    assert not port_is_open("127.0.0.1", port)


def test_write_panel_html_is_standalone_file(tmp_path):
    ideas = [
        {
            "symbol": "002005",
            "name": "测试",
            "board_cn": "深证主板",
            "score": 0.4,
            "action": "buy",
            "shares": 100,
            "stop_loss": 9.1,
            "take_profit": 11.2,
            "ci_p10": -0.02,
            "ci_p50": 0.01,
            "ci_p90": 0.05,
            "flags": "risk_budget",
        }
    ]
    path = write_panel_html(tmp_path, ideas=ideas, snap={"asof": "2025-06-30", "n_buy": 1, "disclaimer": "测试"})
    text = path.read_text(encoding="utf-8")
    assert path.name == "panel.html"
    assert "002005" in text
    assert "file://" not in text
    assert "localhost" not in text
    assert "止损" in text
    assert "buy" in text
