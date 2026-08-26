"""Fetch current A-share bars from East Money public quotes (stdlib HTTP).

Used by the desktop app so the signal date is the latest Shanghai session,
including an overlay of the live last price while the market is open.
Never silently falls back to synthetic demo data.
"""

from __future__ import annotations

import json
import ssl
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

from ..calendar import now_shanghai, session_clock
from ..config import AppConfig, Board
from ..market.rules import classify_limit, limit_ratio
from ..universe.boards import infer_board, is_st_name, is_supported_ashare
from .schema import ensure_bars, meta_from_bars

CLIST_URL = "https://push2.eastmoney.com/api/qt/clist/get"
KLINE_URL = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
UT = "fa5fd1943c7b386f172d6893dbfba10b"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://quote.eastmoney.com/",
    "Accept": "application/json,text/plain,*/*",
}
# SSE/SZSE main + ChiNext + STAR (exclude BJ / B-share)
A_SHARE_FS = "m:0+t:6,m:0+t:80,m:1+t:2,m:1+t:23"
SPOT_FIELDS = "f2,f3,f5,f6,f12,f13,f14,f15,f16,f17,f18,f20,f21,f26"
KLINE_FIELDS1 = "f1,f2,f3,f4,f5,f6"
KLINE_FIELDS2 = "f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61"
INDEX_SECID = "1.000001"

_SSL = ssl.create_default_context()


class LiveDataError(RuntimeError):
    """Raised when live quotes cannot be loaded. Do not catch-and-synthesize."""


def _num(value: Any, default: float | None = None) -> float | None:
    if value is None or value == "" or value == "-":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_listing(value: Any) -> date | None:
    if value is None or value == "" or value == "-":
        return None
    text = str(int(value)) if isinstance(value, (int, float)) else str(value).strip()
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return date(int(text[:4]), int(text[4:6]), int(text[6:8]))
    except ValueError:
        return None


def http_get_json(url: str, params: dict[str, Any], timeout: float = 20.0, retries: int = 4) -> dict:
    query = dict(params)
    query.setdefault("ut", UT)
    full = url + "?" + urlencode(query)
    last: Exception | None = None
    for attempt in range(max(1, retries)):
        try:
            req = Request(full, headers=HEADERS)
            with urlopen(req, timeout=timeout, context=_SSL) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            if raw.startswith("(") and raw.endswith(")"):
                raw = raw[1:-1]
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise LiveDataError("行情接口返回了无法解析的数据")
            return data
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ConnectionError, OSError) as exc:
            last = exc
            time.sleep(0.45 * (attempt + 1))
    raise LiveDataError(f"拉不到实时行情（网络或行情源不可用）：{last}") from last


def _secid(code: str, market: int | None) -> str:
    if market is not None:
        return f"{int(market)}.{code}"
    return f"1.{code}" if code.startswith("6") else f"0.{code}"


def fetch_spot_list(cfg: AppConfig | None = None, http_get: Callable = http_get_json) -> list[dict]:
    cfg = cfg or AppConfig()
    timeout = float(cfg.data.timeout_sec)
    retries = int(cfg.data.retries)
    scan = max(40, int(cfg.data.live_scan))
    page_size = 100
    pages = max(1, (scan + page_size - 1) // page_size)
    rows: list[dict] = []
    total = None
    for pn in range(1, pages + 1):
        payload = http_get(
            CLIST_URL,
            {
                "pn": pn,
                "pz": page_size,
                "po": 1,
                "np": 1,
                "fltt": 2,
                "invt": 2,
                "fid": "f21",
                "fs": A_SHARE_FS,
                "fields": SPOT_FIELDS,
            },
            timeout=timeout,
            retries=retries,
        )
        if int(payload.get("rc") or 0) != 0:
            raise LiveDataError(f"行情列表失败 rc={payload.get('rc')}")
        block = payload.get("data") or {}
        if total is None:
            total = int(block.get("total") or 0)
        diff = block.get("diff") or []
        if isinstance(diff, dict):
            diff = list(diff.values())
        if not diff:
            break
        rows.extend(diff)
        if total is not None and pn * page_size >= total:
            break
        if len(rows) >= scan:
            break
    return rows[:scan]


def fetch_klines(secid: str, cfg: AppConfig | None = None, http_get: Callable = http_get_json) -> list[str]:
    cfg = cfg or AppConfig()
    payload = http_get(
        KLINE_URL,
        {
            "secid": secid,
            "klt": 101,
            "fqt": 1,
            "beg": cfg.data.live_kline_begin,
            "end": "20500101",
            "fields1": KLINE_FIELDS1,
            "fields2": KLINE_FIELDS2,
        },
        timeout=float(cfg.data.timeout_sec),
        retries=int(cfg.data.retries),
    )
    if int(payload.get("rc") or 0) != 0:
        raise LiveDataError(f"K线失败 {secid} rc={payload.get('rc')}")
    klines = (payload.get("data") or {}).get("klines") or []
    return list(klines)


def fetch_index_closes(cfg: AppConfig | None = None, http_get: Callable = http_get_json) -> dict[date, float]:
    try:
        klines = fetch_klines(INDEX_SECID, cfg, http_get=http_get)
    except LiveDataError:
        return {}
    out: dict[date, float] = {}
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 3:
            continue
        try:
            d = date.fromisoformat(parts[0])
            close = float(parts[2])
        except (ValueError, TypeError):
            continue
        out[d] = close
    return out


def _spot_records(raw_rows: list[dict], asof: date, cfg: AppConfig) -> list[dict]:
    picked: list[dict] = []
    for item in raw_rows:
        code = str(item.get("f12") or "").zfill(6)
        if not is_supported_ashare(code):
            continue
        name = str(item.get("f14") or "")
        if cfg.universe.exclude_st and is_st_name(name):
            continue
        board = infer_board(code)
        if board is None or board not in set(cfg.universe.boards):
            continue
        price = _num(item.get("f2"))
        if price is None or price <= 0:
            continue
        listing = _parse_listing(item.get("f26"))
        if listing is None:
            continue
        if (asof - listing).days < cfg.universe.min_listing_days:
            continue
        mcap = _num(item.get("f20"), 0.0) or 0.0
        circ = _num(item.get("f21"), 0.0) or 0.0
        if mcap < cfg.universe.min_market_cap:
            continue
        picked.append(
            {
                "symbol": code,
                "name": name,
                "board": board,
                "market": int(_num(item.get("f13"), 1 if code.startswith("6") else 0) or 0),
                "price": price,
                "open": _num(item.get("f17"), price) or price,
                "high": _num(item.get("f15"), price) or price,
                "low": _num(item.get("f16"), price) or price,
                "prev_close": _num(item.get("f18"), price) or price,
                "volume_lots": _num(item.get("f5"), 0.0) or 0.0,
                "amount": _num(item.get("f6"), 0.0) or 0.0,
                "mcap": mcap,
                "circ": circ,
                "listing_date": listing,
                "is_st": is_st_name(name),
                "secid": _secid(code, int(_num(item.get("f13"), 1 if code.startswith("6") else 0) or 0)),
            }
        )
    picked.sort(key=lambda r: r["circ"] or r["mcap"], reverse=True)
    return picked


def _rows_from_klines(spot: dict, klines: list[str], bench: dict[date, float], cfg: AppConfig) -> list[dict]:
    board: Board = spot["board"]
    shares_out = spot["mcap"] / spot["price"] if spot["price"] else 0.0
    float_shares = spot["circ"] / spot["price"] if spot["price"] else shares_out
    rows: list[dict] = []
    prev_close = None
    for line in klines:
        parts = str(line).split(",")
        if len(parts) < 7:
            continue
        try:
            d = date.fromisoformat(parts[0])
            o, c, h, l = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
            volume = float(parts[5] or 0) * 100.0  # 手 → 股
            amount = float(parts[6] or 0)
        except (ValueError, TypeError):
            continue
        if prev_close is None:
            prev_close = o
        listing_days = max(0, (d - spot["listing_date"]).days)
        ratio = limit_ratio(board, is_st=bool(spot["is_st"]), listing_days=listing_days, cfg=cfg.market)
        status = classify_limit(o, h, l, c, prev_close, ratio)
        rows.append(
            {
                "date": d,
                "symbol": spot["symbol"],
                "open": round(o, 2),
                "high": round(h, 2),
                "low": round(l, 2),
                "close": round(c, 2),
                "volume": round(volume, 0),
                "amount": round(amount, 2),
                "market_cap": round(shares_out * c, 2),
                "float_shares": float_shares,
                "suspended": bool(volume <= 0 and amount <= 0),
                "limit_status": status.value,
                "board": board.value,
                "name": spot["name"],
                "listing_date": spot["listing_date"],
                "is_st": bool(spot["is_st"]),
                "benchmark_close": bench.get(d, c),
            }
        )
        prev_close = c
    return rows


def overlay_spot_bar(rows: list[dict], spot: dict, session_date: date, cfg: AppConfig) -> list[dict]:
    if not rows or spot["price"] is None:
        return rows
    last = rows[-1]
    last_d = last["date"] if not isinstance(last["date"], datetime) else last["date"].date()
    if isinstance(last_d, datetime):
        last_d = last_d.date()
    o = float(spot["open"])
    h = float(spot["high"])
    l = float(spot["low"])
    c = float(spot["price"])
    volume = float(spot["volume_lots"]) * 100.0
    amount = float(spot["amount"])
    shares_out = spot["mcap"] / spot["price"]
    listing_days = max(0, (session_date - spot["listing_date"]).days)
    ratio = limit_ratio(spot["board"], is_st=bool(spot["is_st"]), listing_days=listing_days, cfg=cfg.market)
    prev = float(spot["prev_close"] or last["close"])
    status = classify_limit(o, h, l, c, prev, ratio)
    bar = {
        "date": session_date,
        "symbol": spot["symbol"],
        "open": round(o, 2),
        "high": round(max(h, o, c), 2),
        "low": round(min(l, o, c), 2),
        "close": round(c, 2),
        "volume": round(volume, 0),
        "amount": round(amount, 2),
        "market_cap": round(shares_out * c, 2),
        "float_shares": last["float_shares"],
        "suspended": bool(volume <= 0 and amount <= 0),
        "limit_status": status.value,
        "board": last["board"],
        "name": spot["name"],
        "listing_date": spot["listing_date"],
        "is_st": bool(spot["is_st"]),
        "benchmark_close": last.get("benchmark_close", c),
    }
    if last_d == session_date:
        rows[-1] = bar
    elif last_d < session_date:
        rows.append(bar)
    return rows


def fetch_live_market(
    cfg: AppConfig | None = None,
    *,
    http_get: Callable = http_get_json,
    now: datetime | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    cfg = cfg or AppConfig()
    clock = session_clock(now)
    asof: date = clock["session_date"]
    raw = fetch_spot_list(cfg, http_get=http_get)
    if not raw:
        raise LiveDataError("行情列表为空。请检查网络后重试，系统不会用演示数据充数。")
    spots = _spot_records(raw, asof, cfg)
    limit = max(16, int(cfg.data.live_max_symbols))
    spots = spots[:limit]
    if len(spots) < 8:
        raise LiveDataError(
            f"实时股票池过小（{len(spots)} 只）。请检查网络后重试，系统不会用去年的演示数据充数。"
        )

    bench = fetch_index_closes(cfg, http_get=http_get)
    workers = max(1, int(cfg.data.kline_workers))
    frames: list[pd.DataFrame] = []
    errors: list[str] = []

    def _one(spot: dict) -> pd.DataFrame | None:
        klines = fetch_klines(spot["secid"], cfg, http_get=http_get)
        rows = _rows_from_klines(spot, klines, bench, cfg)
        if len(rows) < 40:
            return None
        rows = overlay_spot_bar(rows, spot, asof, cfg)
        return pd.DataFrame(rows)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(_one, spot): spot for spot in spots}
        for fut in as_completed(futs):
            spot = futs[fut]
            try:
                df = fut.result()
            except Exception as exc:  # noqa: BLE001 — isolate per-symbol HTTP failures
                errors.append(f"{spot['symbol']}: {exc}")
                continue
            if df is not None and not df.empty:
                frames.append(df)

    if len(frames) < 8:
        detail = "；".join(errors[:6])
        raise LiveDataError(
            f"实时日线不足（成功 {len(frames)} 只）。不会用演示数据代替。"
            + (f" 原因：{detail}" if detail else " 请检查网络后重试。")
        )

    bars = ensure_bars(pd.concat(frames, ignore_index=True))
    if bench:
        mapped = bars["date"].dt.date.map(lambda d: bench.get(d))
        bars["benchmark_close"] = mapped.fillna(bars["benchmark_close"])
    meta = meta_from_bars(bars)
    info = {
        "source": "eastmoney_live",
        "source_cn": "东方财富实时行情",
        "quote_time": now_shanghai(clock["now"]).strftime("%Y-%m-%d %H:%M:%S +08:00"),
        "note": clock["note"],
        "intraday": bool(clock["intraday"]),
        "n_symbols": int(bars["symbol"].nunique()),
        "asof": asof.isoformat(),
    }
    return bars, meta, info
