from pathlib import Path

from ashare_quant.desktop import load_idea_rows
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
