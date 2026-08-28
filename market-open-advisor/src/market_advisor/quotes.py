"""Public daily bars from Yahoo, Tencent, Sina, then East Money.

These are the same exchange prints Tonghuashun displays. This module does
not scrape the Tonghuashun client.
"""

from __future__ import annotations

import json
import ssl
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import numpy as np

from .markets import MARKETS, Market

KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
SPOT_URL = "https://push2.eastmoney.com/api/qt/ulist/get"
YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
SINA_KLINE = "https://money.finance.sina.com.cn/quotes_service/api/json_v2.php/CN_MarketData.getKLineData"
TENCENT_KLINE = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
UT = "fa5fd1943c7b386f172d6893dbfba10b"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
}
_SSL = ssl.create_default_context()


class QuoteError(RuntimeError):
    """Live quotes could not be loaded."""


HttpGet = Callable[[str, dict[str, Any]], Any]


def http_get_json(url: str, params: dict[str, Any], timeout: float = 18.0, retries: int = 2) -> Any:
    query = dict(params)
    headers = dict(HEADERS)
    if "eastmoney.com" in url:
        query.setdefault("ut", UT)
        headers["Referer"] = "https://quote.eastmoney.com/"
    elif "sina.com.cn" in url:
        headers["Referer"] = "https://finance.sina.com.cn/"
    elif "gtimg.cn" in url:
        headers["Referer"] = "https://finance.qq.com/"
    elif "yahoo.com" in url:
        headers["Referer"] = "https://finance.yahoo.com/"
    full = url if not query else url + "?" + urlencode(query)
    last: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            req = Request(full, headers=headers)
            with urlopen(req, timeout=timeout, context=_SSL) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if raw.startswith("(") and raw.endswith(")"):
                raw = raw[1:-1]
            data = json.loads(raw)
            return data
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ConnectionError, OSError) as exc:
            last = exc
            time.sleep(0.25 * (attempt + 1))
    raise QuoteError(f"拉不到公开行情：{last}") from last


@dataclass
class BarSeries:
    market: Market
    name: str
    dates: list[str]
    closes: np.ndarray
    spot: float | None
    change_pct: float | None
    fetched_at: str
    source: str


def _as_bars(dates: list[str], closes: list[float]) -> tuple[list[str], np.ndarray]:
    if len(closes) < 80:
        raise QuoteError(f"历史K线过短（{len(closes)} 根），无法拟合模型")
    return dates, np.asarray(closes, dtype=np.float64)


def _change_from_closes(closes: np.ndarray, spot: float | None) -> float | None:
    if len(closes) < 2:
        return None
    last = float(closes[-1])
    prev = float(closes[-2])
    if last == 0 or prev == 0:
        return None
    if spot is None or abs(float(spot) - last) / last < 5e-4:
        return float((last / prev - 1.0) * 100.0)
    return float((float(spot) / last - 1.0) * 100.0)


def parse_eastmoney_klines(klines: list[str]) -> tuple[list[str], np.ndarray]:
    dates: list[str] = []
    closes: list[float] = []
    for row in klines:
        parts = str(row).split(",")
        if len(parts) < 3:
            continue
        try:
            close = float(parts[2])
        except ValueError:
            continue
        dates.append(parts[0])
        closes.append(close)
    return _as_bars(dates, closes)


def parse_yahoo_chart(payload: dict) -> tuple[str, list[str], np.ndarray, float | None, float | None]:
    chart = payload.get("chart") or {}
    if chart.get("error"):
        raise QuoteError(f"Yahoo 返回错误：{chart.get('error')}")
    results = chart.get("result") or []
    if not results:
        raise QuoteError("Yahoo 没有K线")
    result = results[0]
    meta = result.get("meta") or {}
    name = str(meta.get("shortName") or meta.get("longName") or meta.get("symbol") or "")
    timestamps = result.get("timestamp") or []
    quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    raw_closes = quote.get("close") or []
    dates: list[str] = []
    closes: list[float] = []
    for ts, close in zip(timestamps, raw_closes):
        if close is None:
            continue
        dates.append(datetime.fromtimestamp(int(ts), tz=timezone.utc).date().isoformat())
        closes.append(float(close))
    arr_dates, arr = _as_bars(dates, closes)
    spot = meta.get("regularMarketPrice")
    spot_f = float(spot) if spot not in (None, "") else float(arr[-1])
    chg = _change_from_closes(arr, spot_f)
    return name, arr_dates, arr, spot_f, chg


def parse_sina_klines(payload: Any, fallback_name: str) -> tuple[str, list[str], np.ndarray, float | None, float | None]:
    if not isinstance(payload, list) or not payload:
        raise QuoteError("新浪没有K线")
    dates: list[str] = []
    closes: list[float] = []
    for row in payload:
        try:
            dates.append(str(row["day"])[:10])
            closes.append(float(row["close"]))
        except (KeyError, TypeError, ValueError):
            continue
    arr_dates, arr = _as_bars(dates, closes)
    return fallback_name, arr_dates, arr, float(arr[-1]), _change_from_closes(arr, float(arr[-1]))


def parse_tencent_kline(payload: dict, symbol: str, fallback_name: str) -> tuple[str, list[str], np.ndarray, float | None, float | None]:
    data = (payload.get("data") or {}).get(symbol) or {}
    rows = data.get("day") or data.get("qfqday") or []
    dates: list[str] = []
    closes: list[float] = []
    for row in rows:
        if not row or len(row) < 3:
            continue
        try:
            dates.append(str(row[0])[:10])
            closes.append(float(row[2]))
        except (TypeError, ValueError):
            continue
    arr_dates, arr = _as_bars(dates, closes)
    name = fallback_name
    spot = float(arr[-1])
    qt = (data.get("qt") or {}).get(symbol) or []
    if isinstance(qt, list) and len(qt) >= 4:
        if qt[1]:
            name = str(qt[1])
        try:
            spot = float(qt[3])
        except (TypeError, ValueError):
            pass
    return name, arr_dates, arr, spot, _change_from_closes(arr, spot)


def fetch_yahoo(market: Market, http_get: HttpGet = http_get_json) -> BarSeries:
    if not market.yahoo:
        raise QuoteError("该场所没有 Yahoo 代码")
    payload = http_get(YAHOO_CHART.format(symbol=quote(market.yahoo, safe="")), {"interval": "1d", "range": "2y"})
    if not isinstance(payload, dict):
        raise QuoteError("Yahoo 返回无法解析")
    name, dates, closes, spot, chg = parse_yahoo_chart(payload)
    return _series(market, name or market.name, dates, closes, spot, chg, "yahoo")


def fetch_sina(market: Market, http_get: HttpGet = http_get_json) -> BarSeries:
    if not market.sina:
        raise QuoteError("该场所没有新浪代码")
    payload = http_get(SINA_KLINE, {"symbol": market.sina, "scale": "240", "ma": "no", "datalen": "520"})
    name, dates, closes, spot, chg = parse_sina_klines(payload, market.name)
    return _series(market, name, dates, closes, spot, chg, "sina")


def fetch_tencent(market: Market, http_get: HttpGet = http_get_json) -> BarSeries:
    if not market.tencent:
        raise QuoteError("该场所没有腾讯代码")
    payload = http_get(TENCENT_KLINE, {"param": f"{market.tencent},day,,,520,qfq"})
    if not isinstance(payload, dict):
        raise QuoteError("腾讯返回无法解析")
    name, dates, closes, spot, chg = parse_tencent_kline(payload, market.tencent, market.name)
    return _series(market, name, dates, closes, spot, chg, "tencent")


def fetch_eastmoney(market: Market, http_get: HttpGet = http_get_json) -> BarSeries:
    payload = http_get(
        KLINE_URL,
        {
            "secid": market.secid,
            "klt": "101",
            "fqt": "1",
            "lmt": "520",
            "end": "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61",
        },
    )
    if not isinstance(payload, dict):
        raise QuoteError("东方财富返回无法解析")
    data = payload.get("data") or {}
    name = str(data.get("name") or market.name)
    dates, closes = parse_eastmoney_klines(data.get("klines") or [])
    spot = float(closes[-1])
    chg = _change_from_closes(closes, spot)
    try:
        spots = http_get(
            SPOT_URL,
            {"secids": market.secid, "fields": "f2,f3,f12,f13,f14"},
        )
        diff = ((spots.get("data") or {}).get("diff")) or []
        if diff:
            last = diff[0].get("f2")
            pct = diff[0].get("f3")
            if last not in (None, "", "-"):
                spot = float(last)
            if pct not in (None, "", "-"):
                chg = float(pct)
    except QuoteError:
        pass
    return _series(market, name, dates, closes, spot, chg, "eastmoney")


FETCHERS = (fetch_tencent, fetch_sina, fetch_yahoo, fetch_eastmoney)


def _series(
    market: Market,
    name: str,
    dates: list[str],
    closes: np.ndarray,
    spot: float | None,
    chg: float | None,
    source: str,
) -> BarSeries:
    return BarSeries(
        market=market,
        name=name,
        dates=dates,
        closes=closes,
        spot=spot,
        change_pct=chg,
        fetched_at="",
        source=source,
    )


def fetch_market(market: Market, http_get: HttpGet = http_get_json) -> BarSeries:
    errors: list[str] = []
    for fetcher in FETCHERS:
        try:
            return fetcher(market, http_get=http_get)
        except QuoteError as exc:
            errors.append(f"{fetcher.__name__}: {exc}")
    raise QuoteError("；".join(errors))


def load_all(http_get: HttpGet = http_get_json, now: datetime | None = None) -> list[BarSeries]:
    stamp = (now or datetime.now()).isoformat(timespec="seconds")
    series: list[BarSeries] = []
    errors: list[str] = []
    for market in MARKETS:
        try:
            item = fetch_market(market, http_get=http_get)
            item.fetched_at = stamp
            series.append(item)
        except QuoteError as exc:
            errors.append(f"{market.name}: {exc}")
    if not series:
        raise QuoteError("全部交易场所行情均失败：" + "；".join(errors))
    return series


# Backward-compatible names used by older tests.
_parse_klines = parse_eastmoney_klines
