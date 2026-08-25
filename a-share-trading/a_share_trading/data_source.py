from __future__ import annotations

import json
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx
import numpy as np

from .boards import BoardInfo, classify_board, tencent_symbol
from . import config


@dataclass
class Stock:
    code: str
    name: str
    symbol: str
    last: float
    open: float
    high: float
    low: float
    prev_close: float
    change_pct: float
    volume: float
    amount: float
    pe: float | None
    pb: float | None
    mktcap: float | None
    float_mktcap: float | None
    turnover: float | None
    exchange: str
    board: str
    limit_pct: float
    lot_size: int

    @property
    def board_info(self) -> BoardInfo:
        return BoardInfo(self.exchange, self.board, self.limit_pct, self.lot_size)


@dataclass
class Bars:
    symbol: str
    dates: np.ndarray
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray
    source: str = "live"

    def __len__(self) -> int:
        return int(self.close.shape[0])

    @property
    def last_close(self) -> float:
        return float(self.close[-1])


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
        return float(value)
    text = str(value).strip()
    if text in {"", "-", "N/A", "None", "nan"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _client() -> httpx.Client:
    return httpx.Client(
        timeout=httpx.Timeout(20.0, connect=10.0),
        headers={"User-Agent": config.USER_AGENT, "Referer": "https://finance.sina.com.cn/"},
        follow_redirects=True,
    )


def fetch_universe(force: bool = False) -> list[Stock]:
    if config.UNIVERSE_PATH.exists() and not force:
        return load_universe()

    stocks: list[Stock] = []
    with _client() as client:
        count_raw = client.get(config.SINA_COUNT_URL).text.strip().strip('"')
        total = int(count_raw)
        page_size = 100
        pages = math.ceil(total / page_size)
        for page in range(1, pages + 1):
            for attempt in range(4):
                try:
                    resp = client.get(
                        config.SINA_LIST_URL,
                        params={
                            "page": page,
                            "num": page_size,
                            "sort": "symbol",
                            "asc": 1,
                            "node": "hs_a",
                        },
                    )
                    resp.raise_for_status()
                    rows = resp.json()
                    break
                except Exception:
                    if attempt == 3:
                        raise
                    time.sleep(0.6 * (attempt + 1))
            if not isinstance(rows, list):
                continue
            for row in rows:
                stock = _row_to_stock(row)
                if stock is not None:
                    stocks.append(stock)
            time.sleep(0.05)

    stocks.sort(key=lambda s: s.symbol)
    save_universe(stocks)
    return stocks


def _row_to_stock(row: dict[str, Any]) -> Stock | None:
    code = str(row.get("code") or "").zfill(6)
    symbol = str(row.get("symbol") or "")
    name = str(row.get("name") or "")
    if not code or not symbol:
        return None
    board = classify_board(code, name)
    last = _to_float(row.get("trade")) or 0.0
    return Stock(
        code=code,
        name=name,
        symbol=symbol,
        last=last,
        open=_to_float(row.get("open")) or 0.0,
        high=_to_float(row.get("high")) or 0.0,
        low=_to_float(row.get("low")) or 0.0,
        prev_close=_to_float(row.get("settlement")) or last,
        change_pct=_to_float(row.get("changepercent")) or 0.0,
        volume=_to_float(row.get("volume")) or 0.0,
        amount=_to_float(row.get("amount")) or 0.0,
        pe=_to_float(row.get("per")),
        pb=_to_float(row.get("pb")),
        mktcap=_to_float(row.get("mktcap")),
        float_mktcap=_to_float(row.get("nmc")),
        turnover=_to_float(row.get("turnoverratio")),
        exchange=board.exchange,
        board=board.board,
        limit_pct=board.limit_pct,
        lot_size=board.lot_size,
    )


def save_universe(stocks: Iterable[Stock]) -> None:
    payload = [asdict(s) for s in stocks]
    config.UNIVERSE_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def load_universe() -> list[Stock]:
    raw = json.loads(config.UNIVERSE_PATH.read_text(encoding="utf-8"))
    return [Stock(**row) for row in raw]


def _bars_path(symbol: str) -> Path:
    return config.BARS_DIR / f"{symbol}.npz"


def save_bars(bars: Bars) -> None:
    np.savez_compressed(
        _bars_path(bars.symbol),
        dates=bars.dates.astype("U10"),
        open=bars.open.astype(np.float64),
        high=bars.high.astype(np.float64),
        low=bars.low.astype(np.float64),
        close=bars.close.astype(np.float64),
        volume=bars.volume.astype(np.float64),
        source=np.array(bars.source),
    )


def load_bars(symbol: str) -> Bars | None:
    path = _bars_path(symbol)
    if not path.exists():
        return None
    with np.load(path, allow_pickle=False) as data:
        return Bars(
            symbol=symbol,
            dates=data["dates"],
            open=data["open"],
            high=data["high"],
            low=data["low"],
            close=data["close"],
            volume=data["volume"],
            source=str(data["source"]) if "source" in data.files else "live",
        )


def fetch_kline(symbol: str, count: int = config.HISTORY_BARS, client: httpx.Client | None = None) -> Bars | None:
    own = client is None
    if own:
        client = _client()
    try:
        resp = client.get(
            config.TENCENT_KLINE_URL,
            params={"param": f"{symbol},day,,,{count},qfq"},
            headers={"Referer": "https://finance.qq.com/"},
        )
        resp.raise_for_status()
        payload = resp.json()
        node = (payload.get("data") or {}).get(symbol) or {}
        rows = node.get("qfqday") or node.get("day") or []
        if not rows:
            return None
        dates, o, h, l, c, v = [], [], [], [], [], []
        for row in rows:
            dates.append(str(row[0])[:10])
            o.append(float(row[1]))
            c.append(float(row[2]))
            h.append(float(row[3]))
            l.append(float(row[4]))
            v.append(float(row[5]))
        bars = Bars(
            symbol=symbol,
            dates=np.array(dates),
            open=np.array(o, dtype=np.float64),
            high=np.array(h, dtype=np.float64),
            low=np.array(l, dtype=np.float64),
            close=np.array(c, dtype=np.float64),
            volume=np.array(v, dtype=np.float64),
            source="live",
        )
        save_bars(bars)
        return bars
    except Exception:
        return None
    finally:
        if own:
            client.close()


def fetch_all_klines(
    stocks: list[Stock],
    count: int = config.HISTORY_BARS,
    max_workers: int = 16,
    resume: bool = True,
    limit: int | None = None,
) -> dict[str, str]:
    targets = stocks[:limit] if limit else stocks
    if limit:
        targets = sorted(stocks, key=lambda s: (s.mktcap or 0), reverse=True)[:limit]
    stats = {"ok": 0, "skip": 0, "fail": 0}

    def _one(stock: Stock) -> str:
        if resume and _bars_path(stock.symbol).exists():
            return "skip"
        with _client() as client:
            bars = fetch_kline(stock.symbol, count=count, client=client)
        return "ok" if bars is not None and len(bars) >= 10 else "fail"

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(_one, s): s.symbol for s in targets}
        for fut in as_completed(futs):
            status = fut.result()
            stats[status] = stats.get(status, 0) + 1
    return stats


def synthesize_bars(stock: Stock, n: int = config.HISTORY_BARS, seed: int | None = None) -> Bars:
    """Deterministic GBM-like path ending at the last print, with A-share limits."""
    rng = np.random.default_rng(seed if seed is not None else _stable_seed(stock.code))
    n = max(n, config.MIN_BARS)
    last = stock.last if stock.last > 0 else 10.0
    mu = 0.00015
    vol = float(np.clip(abs(stock.change_pct) / 100.0 * 1.8, 0.016, 0.035))
    shocks = rng.normal(mu, vol, size=n)
    # mild AR(1) plus occasional jump
    for i in range(1, n):
        shocks[i] += 0.08 * shocks[i - 1]
    jumps = rng.random(n) < 0.02
    shocks[jumps] += rng.normal(0, 0.04, size=int(jumps.sum()))
    limit = max(stock.limit_pct, 0.05)
    shocks = np.clip(shocks, -limit + 1e-6, limit - 1e-6)
    rets = shocks[::-1]
    closes = np.empty(n, dtype=np.float64)
    closes[-1] = last
    for i in range(n - 2, -1, -1):
        closes[i] = closes[i + 1] / (1.0 + rets[i + 1])
    opens = np.concatenate([[closes[0]], closes[:-1] * (1 + rng.normal(0, 0.004, n - 1))])
    highs = np.maximum(opens, closes) * (1 + np.abs(rng.normal(0, 0.006, n)))
    lows = np.minimum(opens, closes) * (1 - np.abs(rng.normal(0, 0.006, n)))
    highs = np.maximum(highs, np.maximum(opens, closes))
    lows = np.minimum(lows, np.minimum(opens, closes))
    volume = np.abs(rng.lognormal(mean=13.5, sigma=0.7, size=n))
    if stock.volume > 0:
        volume[-1] = stock.volume
    dates = _business_dates(n)
    return Bars(
        symbol=stock.symbol,
        dates=np.array(dates),
        open=opens,
        high=highs,
        low=lows,
        close=closes,
        volume=volume,
        source="synthetic",
    )


def _stable_seed(code: str) -> int:
    h = 2166136261
    for ch in code.encode("utf-8"):
        h ^= ch
        h = (h * 16777619) & 0xFFFFFFFF
    return int(h)


def _business_dates(n: int) -> list[str]:
    # Generate n weekdays ending 2026-08-25 without pandas DateOffset deps.
    end = np.datetime64("2026-08-25")
    dates: list[str] = []
    cur = end
    while len(dates) < n:
        weekday = int(np.datetime64(cur, "D").astype("datetime64[D]").view("int64") + 4) % 7
        # numpy datetime64 epoch weekday: 0=Thu for 1970-01-01, use pandas-free isoweekday
        py = cur.astype(object)
        if py.weekday() < 5:
            dates.append(str(cur))
        cur -= np.timedelta64(1, "D")
    dates.reverse()
    return dates


def load_or_make_bars(stock: Stock, allow_synthetic: bool = True) -> Bars:
    bars = load_bars(stock.symbol)
    if bars is not None and len(bars) >= config.MIN_BARS:
        return bars
    if allow_synthetic:
        return synthesize_bars(stock)
    raise FileNotFoundError(stock.symbol)
