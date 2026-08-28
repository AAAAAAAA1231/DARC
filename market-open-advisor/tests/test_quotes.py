from datetime import datetime, timezone

import pytest

from market_advisor.markets import MARKETS
from market_advisor.quotes import (
    QuoteError,
    parse_eastmoney_klines,
    parse_sina_klines,
    parse_tencent_kline,
    parse_yahoo_chart,
    load_all,
)
from conftest import synthetic_closes, synthetic_dates


def test_parse_klines_requires_history():
    with pytest.raises(QuoteError):
        parse_eastmoney_klines(["2024-01-01,1,2"] * 10)


def test_parse_klines_ok():
    rows = [f"d{i},100,{100 + i},101,99,1" for i in range(90)]
    dates, closes = parse_eastmoney_klines(rows)
    assert len(dates) == 90
    assert float(closes[-1]) == 189


def test_parse_yahoo_chart():
    start = int(datetime(2025, 1, 2, tzinfo=timezone.utc).timestamp())
    closes = [3000 + i if i != 10 else None for i in range(90)]
    payload = {
        "chart": {
            "result": [
                {
                    "meta": {
                        "shortName": "SSE Composite",
                        "regularMarketPrice": 3090,
                        "chartPreviousClose": 3080,
                    },
                    "timestamp": [start + i * 86400 for i in range(90)],
                    "indicators": {"quote": [{"close": closes}]},
                }
            ]
        }
    }
    name, dates, arr, spot, chg = parse_yahoo_chart(payload)
    assert name == "SSE Composite"
    assert len(arr) == 89
    assert spot == 3090
    # 3090 vs last kept close 3089 (index 89 skipped None at i=10; last raw is 3089)
    assert chg is not None
    assert abs(chg) < 5


def test_parse_sina_and_tencent():
    rows = [{"day": f"2025-01-{1 + i % 27:02d}", "close": str(100 + i)} for i in range(90)]
    name, dates, arr, spot, chg = parse_sina_klines(rows, "上证")
    assert name == "上证"
    assert float(arr[-1]) == 189
    payload = {
        "data": {
            "sh000001": {
                "day": [[d, c, c, c, c, 1] for d, c in zip(dates, arr)],
                "qt": {"sh000001": ["1", "上证指数", "000001", "190.5", "189"]},
            }
        }
    }
    name, dates2, arr2, spot2, _ = parse_tencent_kline(payload, "sh000001", "上证")
    assert name == "上证指数"
    assert spot2 == 190.5


def _yahoo_payload(closes, name="IDX"):
    start = int(datetime(2024, 1, 2, tzinfo=timezone.utc).timestamp())
    return {
        "chart": {
            "result": [
                {
                    "meta": {"shortName": name, "regularMarketPrice": float(closes[-1]), "chartPreviousClose": float(closes[-2])},
                    "timestamp": [start + i * 86400 for i in range(len(closes))],
                    "indicators": {"quote": [{"close": [float(x) for x in closes]}]},
                }
            ]
        }
    }


def test_load_all_falls_back_across_sources():
    closes = synthetic_closes()

    def http_get(url: str, params: dict):
        if "gtimg.cn" in url:
            if "bj899050" in str(params.get("param", "")):
                dates = synthetic_dates(len(closes))
                return {
                    "data": {
                        "bj899050": {
                            "day": [[d, float(c), float(c), float(c), float(c), 1] for d, c in zip(dates, closes)],
                            "qt": {"bj899050": ["1", "北证50", "899050", float(closes[-1]), float(closes[-2])]},
                        }
                    }
                }
            return {"data": {}}
        if "sina.com.cn" in url:
            return []
        if "yahoo.com" in url:
            if "HSI" in url:
                return _yahoo_payload(closes, "HSI")
            if "NDX" in url:
                return _yahoo_payload(closes, "NDX")
            return _yahoo_payload(closes, "A")
        return {}

    series = load_all(http_get=http_get)
    assert len(series) == len(MARKETS)
    sse = next(item for item in series if item.market.key == "sse")
    assert sse.source == "yahoo"
    bse = next(item for item in series if item.market.key == "bse")
    assert bse.source == "tencent"
    assert bse.name == "北证50"
