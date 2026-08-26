from datetime import date, datetime

import pandas as pd
import pytest

from ashare_quant.calendar import SHANGHAI, session_clock
from ashare_quant.config import AppConfig
from ashare_quant.data.eastmoney import (
    LiveDataError,
    fetch_live_market,
    overlay_spot_bar,
)
from ashare_quant.data.provider import MarketData
from ashare_quant.panel_html import write_panel_html
from ashare_quant.pipeline import ensure_market, run_pipeline
from ashare_quant.universe.boards import infer_board


def test_session_clock_uses_shanghai_now():
    open_now = datetime(2026, 8, 26, 14, 19, tzinfo=SHANGHAI)
    clock = session_clock(open_now)
    assert clock["state"] == "open"
    assert clock["intraday"] is True
    assert clock["session_date"] == date(2026, 8, 26)

    sunday = datetime(2026, 8, 23, 10, 0, tzinfo=SHANGHAI)
    closed = session_clock(sunday)
    assert closed["state"] == "closed"
    assert closed["session_date"] == date(2026, 8, 21)
    assert closed["intraday"] is False


def test_overlay_spot_bar_replaces_today():
    listing = date(2012, 4, 10)
    rows = [
        {
            "date": date(2026, 8, 25),
            "symbol": "300308",
            "open": 850.0,
            "high": 871.0,
            "low": 837.0,
            "close": 846.0,
            "volume": 1000,
            "amount": 1e6,
            "market_cap": 1e11,
            "float_shares": 1e8,
            "suspended": False,
            "limit_status": "normal",
            "board": "chinext",
            "name": "中际旭创",
            "listing_date": listing,
            "is_st": False,
            "benchmark_close": 3889.0,
        },
        {
            "date": date(2026, 8, 26),
            "symbol": "300308",
            "open": 855.0,
            "high": 860.0,
            "low": 830.0,
            "close": 851.0,
            "volume": 1000,
            "amount": 1e6,
            "market_cap": 1e11,
            "float_shares": 1e8,
            "suspended": False,
            "limit_status": "normal",
            "board": "chinext",
            "name": "中际旭创",
            "listing_date": listing,
            "is_st": False,
            "benchmark_close": 3913.0,
        },
    ]
    spot = {
        "symbol": "300308",
        "name": "中际旭创",
        "board": infer_board("300308"),
        "price": 851.38,
        "open": 855.0,
        "high": 866.0,
        "low": 830.0,
        "prev_close": 846.0,
        "volume_lots": 195277,
        "amount": 1.66e10,
        "mcap": 9.95e11,
        "circ": 9.44e11,
        "listing_date": listing,
        "is_st": False,
    }
    out = overlay_spot_bar(rows, spot, date(2026, 8, 26), AppConfig())
    assert out[-1]["date"] == date(2026, 8, 26)
    assert out[-1]["close"] == 851.38
    assert len(out) == 2


def _kline_lines(start: date, end: date, px: float = 10.0) -> list[str]:
    from ashare_quant.calendar import trading_days

    lines = []
    for i, d in enumerate(trading_days(start, end)):
        price = round(px * (1.0 + 0.0005 * (i % 9 - 4)), 2)
        o = price
        h = round(price * 1.01, 2)
        l = round(price * 0.99, 2)
        vol = 120000
        amt = vol * 100 * price
        lines.append(f"{d.isoformat()},{o:.2f},{price:.2f},{h:.2f},{l:.2f},{vol},{amt:.2f},1,0,0,1")
    return lines


def _fake_http(symbols: list[str], end: date = date(2026, 8, 26)):
    klines = _kline_lines(date(2026, 4, 1), end)
    index_lines = _kline_lines(date(2026, 4, 1), end, px=3800.0)
    spots = []
    for i, code in enumerate(symbols):
        market = 1 if code.startswith("6") else 0
        spots.append(
            {
                "f2": 12.5 + i,
                "f5": 200000,
                "f6": 8.0e8,
                "f12": code,
                "f13": market,
                "f14": f"测试{code}",
                "f15": 13.0 + i,
                "f16": 12.0 + i,
                "f17": 12.4 + i,
                "f18": 12.3 + i,
                "f20": 5.0e10,
                "f21": 4.0e10,
                "f26": 20100101,
            }
        )

    def http_get(url, params, timeout=20.0, retries=4):
        if "clist" in url:
            return {"rc": 0, "data": {"total": len(spots), "diff": spots}}
        secid = str(params.get("secid") or "")
        if secid == "1.000001":
            return {"rc": 0, "data": {"name": "上证指数", "klines": index_lines}}
        return {"rc": 0, "data": {"klines": klines}}

    return http_get


def test_fetch_live_market_mocked_asof_is_today():
    cfg = AppConfig()
    cfg.data.live_max_symbols = 10
    cfg.data.kline_workers = 2
    cfg.universe.min_listing_days = 30
    cfg.universe.min_market_cap = 1e9
    symbols = ["600000", "601398", "000001", "002415", "300750", "688981", "603259", "000858", "300124", "601318"]
    now = datetime(2026, 8, 26, 14, 19, tzinfo=SHANGHAI)
    bars, meta, info = fetch_live_market(cfg, http_get=_fake_http(symbols), now=now)
    assert info["source"] == "eastmoney_live"
    assert info["asof"] == "2026-08-26"
    assert pd.to_datetime(bars["date"]).max().date() == date(2026, 8, 26)
    assert bars["symbol"].nunique() >= 8
    last = bars.sort_values("date").groupby("symbol").tail(1)
    assert (last["close"] > 0).all()


def test_live_http_failure_does_not_synthesize(tiny_cfg, tmp_path, monkeypatch):
    cfg = tiny_cfg.model_copy(deep=True)
    cfg.data.source = "live"

    def boom(cls, cfg=None, **kwargs):
        raise LiveDataError("拉不到实时行情（网络或行情源不可用）")

    monkeypatch.setattr("ashare_quant.pipeline.MarketData.live", classmethod(boom))
    with pytest.raises(LiveDataError, match="实时行情"):
        ensure_market(cfg, tmp_path / "live_bars.csv", regenerate=True)
    assert not (tmp_path / "live_bars.csv").exists()
    assert not (tmp_path / "synthetic_bars.csv").exists()


def test_explicit_csv_skips_live(tiny_cfg, tiny_market, tmp_path, monkeypatch):
    bars, meta = tiny_market
    path = tmp_path / "bars.csv"
    MarketData(bars, meta).save(path)

    def boom(cls, cfg=None, **kwargs):
        raise AssertionError("must not hit live API")

    monkeypatch.setattr("ashare_quant.pipeline.MarketData.live", classmethod(boom))
    loaded = ensure_market(tiny_cfg, path, regenerate=False)
    assert loaded.live_info.get("source") == "csv"
    assert pd.to_datetime(loaded.bars["date"]).max().date().year == 2024


def test_pipeline_live_asof_is_current_session(tiny_cfg, tiny_market, tmp_path, monkeypatch):
    bars, meta = tiny_market
    shifted = bars.copy()
    delta = pd.Timestamp("2026-08-26") - pd.to_datetime(shifted["date"]).max()
    shifted["date"] = pd.to_datetime(shifted["date"]) + delta
    live = MarketData(
        shifted,
        meta,
        live_info={
            "source": "eastmoney_live",
            "source_cn": "东方财富实时行情",
            "quote_time": "2026-08-26 14:19:00 +08:00",
            "note": "盘中最新价（2026-08-26 14:19 上海时间），不是收盘价",
        },
    )

    def fake_live(cls, cfg=None, **kwargs):
        return live

    monkeypatch.setattr("ashare_quant.pipeline.MarketData.live", classmethod(fake_live))
    cfg = tiny_cfg.model_copy(deep=True)
    cfg.data.source = "live"
    result = run_pipeline(
        cfg,
        output_dir=tmp_path / "out",
        data_path=tmp_path / "missing.csv",
        mode="quick",
    )
    assert result.asof == "2026-08-26"
    snap = result.extra["snapshot"]
    assert snap["data_source"] == "eastmoney_live"
    assert snap["asof"] != "2025-06-30"
    assert "2026-08-26" in snap["quote_time"]
    html = write_panel_html(tmp_path / "out", ideas=result.ideas.to_dict(orient="records"), snap=snap)
    text = html.read_text(encoding="utf-8")
    assert "2026-08-26" in text
    assert "2025-06-30" not in text
    assert "东方财富实时行情" in text


def test_default_source_is_live():
    assert AppConfig().data.source == "live"


def test_write_panel_html_shows_quote_time(tmp_path):
    path = write_panel_html(
        tmp_path,
        ideas=[{"symbol": "300308", "name": "中际旭创", "action": "buy", "score": 0.4}],
        snap={
            "asof": "2026-08-26",
            "quote_time": "2026-08-26 14:19:00 +08:00",
            "data_source_cn": "东方财富实时行情",
            "n_buy": 1,
            "disclaimer": "测试",
        },
    )
    text = path.read_text(encoding="utf-8")
    assert "2026-08-26" in text
    assert "行情时刻" in text
    assert "东方财富实时行情" in text
    assert "2025-06-30" not in text
