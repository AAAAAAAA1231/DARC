from datetime import datetime

from market_advisor.cli import format_text
from market_advisor.engine import analyze_series, run_report
from market_advisor.markets import MARKETS
from conftest import fake_series


def test_analyze_series_uses_ten_billion_limit():
    item = analyze_series(fake_series(), datetime(2026, 8, 28, 9, 31), n_verify=80_000, seed=1)
    assert item.n_limit_sims == 10_000_000_000
    assert item.n_verify_sims == 80_000
    assert item.action in {"偏多", "观望", "偏空"}
    assert item.market_key == "sse"


def test_run_report_with_injected_http():
    series = fake_series()
    k_closes = [float(x) for x in series.closes]
    start = 1_700_000_000

    def http_get(url: str, params: dict) -> dict:
        if "gtimg.cn" in url:
            key = "bj899050" if "bj899050" in str(params.get("param", "")) else None
            if not key:
                return {"data": {}}
            return {
                "data": {
                    "bj899050": {
                        "day": [[d, c, c, c, c, 1] for d, c in zip(series.dates, k_closes)],
                        "qt": {"bj899050": ["1", "北证50", "899050", k_closes[-1], k_closes[-2]]},
                    }
                }
            }
        if "sina.com.cn" in url:
            return []
        if "yahoo.com" in url:
            return {
                "chart": {
                    "result": [
                        {
                            "meta": {
                                "shortName": "测试指数",
                                "regularMarketPrice": k_closes[-1],
                                "chartPreviousClose": k_closes[-2],
                            },
                            "timestamp": [start + i * 86400 for i in range(len(k_closes))],
                            "indicators": {"quote": [{"close": k_closes}]},
                        }
                    ]
                }
            }
        return {}

    report = run_report(http_get=http_get, now=datetime(2026, 8, 28, 9, 31), n_verify=30_000, seed=2, per_market=0)
    assert len(report.items) == len(MARKETS)
    text = format_text(report)
    assert "打开时刻" in text
    assert "100亿次极限" in text
    assert "投资建议" in report.disclaimer


def test_html_report_contains_venues():
    from pathlib import Path

    from market_advisor.html_report import write_html

    series = fake_series()
    k_closes = [float(x) for x in series.closes]
    start = 1_700_000_000

    def http_get(url: str, params: dict):
        if "gtimg.cn" in url and "bj899050" in str(params.get("param", "")):
            return {
                "data": {
                    "bj899050": {
                        "day": [[d, c, c, c, c, 1] for d, c in zip(series.dates, k_closes)],
                        "qt": {"bj899050": ["1", "北证50", "899050", k_closes[-1], k_closes[-2]]},
                    }
                }
            }
        if "gtimg.cn" in url:
            return {"data": {}}
        if "sina.com.cn" in url:
            return []
        if "yahoo.com" in url:
            return {
                "chart": {
                    "result": [
                        {
                            "meta": {"shortName": "测试指数", "regularMarketPrice": k_closes[-1]},
                            "timestamp": [start + i * 86400 for i in range(len(k_closes))],
                            "indicators": {"quote": [{"close": k_closes}]},
                        }
                    ]
                }
            }
        return {}

    report = run_report(http_get=http_get, now=datetime(2026, 8, 28, 9, 31), n_verify=20_000, seed=2, per_market=0)
    out = Path("/tmp/open-advisor-test.html")
    write_html(report, out)
    html = out.read_text(encoding="utf-8")
    assert "打开时刻个股操作建议" in html
    assert "上交所主板" in html
    assert "100亿极限" in html


def test_run_report_emits_per_stock_rows():
    series = fake_series()
    k_closes = [float(x) for x in series.closes]
    start = 1_700_000_000
    sina_klines = [{"day": d, "close": str(c)} for d, c in zip(series.dates, k_closes)]

    def http_get(url: str, params: dict):
        if "Market_Center.getHQNodeData" in url:
            if params.get("node") == "sh_a":
                return [{"symbol": "sh600519", "code": "600519", "name": "贵州茅台"}]
            return []
        if "CN_MarketData.getKLineData" in url:
            return sina_klines
        if "gtimg.cn" in url and "bj899050" in str(params.get("param", "")):
            return {
                "data": {
                    "bj899050": {
                        "day": [[d, c, c, c, c, 1] for d, c in zip(series.dates, k_closes)],
                        "qt": {"bj899050": ["1", "北证50", "899050", k_closes[-1], k_closes[-2]]},
                    }
                }
            }
        if "gtimg.cn" in url:
            return {"data": {}}
        if "yahoo.com" in url:
            return {
                "chart": {
                    "result": [
                        {
                            "meta": {"shortName": "测试指数", "regularMarketPrice": k_closes[-1]},
                            "timestamp": [start + i * 86400 for i in range(len(k_closes))],
                            "indicators": {"quote": [{"close": k_closes}]},
                        }
                    ]
                }
            }
        return {}

    report = run_report(
        http_get=http_get,
        now=datetime(2026, 8, 28, 9, 31),
        n_verify=8_000,
        seed=2,
        per_market=1,
        stock_verify=0,
    )
    sse = next(item for item in report.items if item.market_key == "sse")
    assert any(stock.symbol == "600519" for stock in sse.stocks)
    text = format_text(report)
    assert "贵州茅台" in text
    assert "个股建议" in text
