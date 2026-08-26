"""Synthetic A-share-like daily bars for tests, demos, and walk-forward.

Real-market adapters can replace this generator; the rest of the stack only
consumes the bar/meta schema. The simulator encodes limit-up/down, occasional
suspension, ST names, IPO seasoning, and liquidity stratification.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd

from ..calendar import trading_days
from ..config import AppConfig, Board
from ..market.rules import classify_limit, limit_prices, limit_ratio
from .schema import ensure_bars, meta_from_bars

_BOARD_SPECS: list[tuple[str, Board, int, float]] = [
    ("600", Board.SSE_MAIN, 14, 1.0),
    ("601", Board.SSE_MAIN, 6, 0.9),
    ("000", Board.SZSE_MAIN, 10, 1.05),
    ("002", Board.SZSE_MAIN, 6, 1.1),
    ("300", Board.CHINEXT, 8, 1.45),
    ("688", Board.STAR, 8, 1.55),
]


def _codes(prefix: str, n: int) -> list[str]:
    out = []
    for i in range(n):
        if prefix in {"600", "601"}:
            out.append(f"{prefix}{i:03d}")
        else:
            out.append(f"{prefix}{i:03d}")
    return [c.ljust(6, "0")[:6] for c in out]


def generate_synthetic_market(
    cfg: AppConfig | None = None,
    *,
    start: date | None = None,
    end: date | None = None,
    seed: int | None = None,
    n_override: dict[str, int] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    cfg = cfg or AppConfig()
    rng = np.random.default_rng(seed if seed is not None else cfg.seed)
    start = start or date(2023, 1, 4)
    end = end or date(2025, 6, 30)
    sessions = trading_days(start, end)
    if len(sessions) < 80:
        raise ValueError("need a longer calendar window for synthetic market")

    names_cn_pool = [
        "华海", "东升", "锦程", "北辰", "远航", "嘉禾", "瑞信", "明德",
        "天成", "弘业", "金桥", "南岭", "星河", "安泰", "和顺", "泽宇",
    ]
    industry = ["电子", "医药", "制造", "材料", "软件", "新能源", "消费", "金融"]

    meta_rows: list[dict] = []
    specs = []
    for prefix, board, n, vol_m in _BOARD_SPECS:
        count = n if not n_override else n_override.get(prefix, n)
        specs.append((prefix, board, count, vol_m))

    serial = 0
    for prefix, board, n, vol_m in specs:
        for i, code in enumerate(_codes(prefix, n)):
            listing = start - timedelta(days=int(rng.integers(80, 1800)))
            # A few recent IPOs and one long-suspended / illiquid / ST per board group
            is_new = serial % 23 == 0
            is_illiquid = serial % 17 == 0
            is_st = serial % 29 == 0
            long_suspend = serial % 31 == 0
            if is_new:
                listing = sessions[max(0, len(sessions) - int(rng.integers(10, 50)))]
            name = f"{names_cn_pool[serial % len(names_cn_pool)]}{industry[serial % len(industry)]}"
            if is_st:
                name = f"ST{name}"
            float_shares = float(rng.uniform(3.5e8, 5.0e9))
            if is_illiquid:
                float_shares *= 0.04
            meta_rows.append(
                {
                    "symbol": code,
                    "name": name,
                    "board": board.value,
                    "listing_date": listing,
                    "is_st": is_st,
                    "float_shares": float_shares,
                    "vol_mult": vol_m,
                    "illiquid": is_illiquid,
                    "long_suspend": long_suspend,
                    "regime": str(rng.choice(["trend", "mr", "mixed"], p=[0.35, 0.30, 0.35])),
                }
            )
            serial += 1

    meta = pd.DataFrame(meta_rows)
    n_days = len(sessions)
    bench_ret = rng.normal(0.00015, 0.012, size=n_days)
    bench = 1000.0 * np.exp(np.cumsum(bench_ret))

    frames: list[pd.DataFrame] = []
    for _, rec in meta.iterrows():
        board = Board(rec["board"])
        n = n_days
        sigma = 0.018 * float(rec["vol_mult"])
        if rec["illiquid"]:
            sigma *= 1.4
        # GARCH-like vol + regime
        z = rng.normal(size=n)
        log_vol = np.zeros(n)
        log_vol[0] = np.log(sigma)
        for t in range(1, n):
            log_vol[t] = 0.94 * log_vol[t - 1] + 0.06 * np.log(sigma) + 0.12 * z[t - 1] * 0.05
        vol = np.exp(log_vol)
        if rec["regime"] == "trend":
            drift = 0.00035 + 0.08 * np.sin(np.linspace(0, 6, n)) / 252
        elif rec["regime"] == "mr":
            drift = np.zeros(n)
        else:
            drift = 0.0001 + rng.normal(0, 0.0002, n)

        px = np.empty(n)
        px[0] = float(rng.uniform(8.0, 48.0))
        rets = np.empty(n)
        rets[0] = 0.0
        for t in range(1, n):
            mean_rev = 0.0
            if rec["regime"] == "mr":
                mean_rev = -0.08 * np.log(px[t - 1] / px[0])
            shock = drift[t] + mean_rev + vol[t] * rng.normal()
            # fat tail
            if rng.random() < 0.015:
                shock += rng.choice([-1.0, 1.0]) * rng.uniform(0.04, 0.09)
            rets[t] = shock
            px[t] = max(1.0, px[t - 1] * np.exp(shock))

        opens = np.empty(n)
        highs = np.empty(n)
        lows = np.empty(n)
        closes = np.empty(n)
        volumes = np.empty(n)
        suspended = np.zeros(n, dtype=bool)
        limit_status = np.array(["normal"] * n, dtype=object)

        suspend_start = None
        if rec["long_suspend"]:
            suspend_start = int(rng.integers(n // 2, n - 15))

        listing_ts = pd.Timestamp(rec["listing_date"])
        for t, sess in enumerate(sessions):
            listing_days = max(0, (sess - listing_ts.date()).days)
            ratio = limit_ratio(board, is_st=bool(rec["is_st"]), listing_days=listing_days, cfg=cfg.market)
            if t == 0:
                prev = px[0]
            else:
                prev = closes[t - 1]
            up, down = limit_prices(prev, ratio)

            if sess < listing_ts.date():
                suspended[t] = True
                o = h = l = c = prev
                vol_shares = 0.0
            elif rec["long_suspend"] and suspend_start is not None and t >= suspend_start:
                suspended[t] = True
                o = h = l = c = prev
                vol_shares = 0.0
            else:
                # open gap then intra-day range
                gap = rng.normal(0, vol[t] * 0.35)
                o = float(np.clip(prev * np.exp(gap), down, up))
                c_raw = float(px[t])
                c = float(np.clip(c_raw, down, up))
                intra = abs(rng.normal(0, vol[t] * prev * 0.6))
                h = float(np.clip(max(o, c) + intra, down, up))
                l = float(np.clip(min(o, c) - intra, down, up))
                if h < max(o, c):
                    h = max(o, c)
                if l > min(o, c):
                    l = min(o, c)
                # rare one-word limit
                if rng.random() < 0.012:
                    direction = 1 if rng.random() < 0.55 else -1
                    cap = up if direction > 0 else down
                    o = h = l = c = cap
                base_vol = rec["float_shares"] * rng.uniform(0.004, 0.02)
                if rec["illiquid"]:
                    base_vol *= 0.08
                volumes[t] = max(0.0, base_vol * (1.0 + 8.0 * abs(np.log(max(c, 1e-6) / prev))))
                vol_shares = volumes[t]
                status = classify_limit(o, h, l, c, prev, ratio)
                limit_status[t] = status.value
                opens[t], highs[t], lows[t], closes[t] = o, h, l, c
                continue

            opens[t] = o
            highs[t] = h
            lows[t] = l
            closes[t] = c
            volumes[t] = vol_shares
            limit_status[t] = classify_limit(o, h, l, c, prev, ratio).value

        amount = volumes * (highs + lows + closes) / 3.0
        mcap = rec["float_shares"] * 1.35 * closes
        frames.append(
            pd.DataFrame(
                {
                    "date": sessions,
                    "symbol": rec["symbol"],
                    "open": np.round(opens, 2),
                    "high": np.round(highs, 2),
                    "low": np.round(lows, 2),
                    "close": np.round(closes, 2),
                    "volume": np.round(volumes, 0),
                    "amount": np.round(amount, 2),
                    "market_cap": np.round(mcap, 2),
                    "float_shares": rec["float_shares"],
                    "suspended": suspended,
                    "limit_status": limit_status,
                    "board": rec["board"],
                    "name": rec["name"],
                    "listing_date": rec["listing_date"],
                    "is_st": rec["is_st"],
                    "benchmark_close": np.round(bench, 2),
                }
            )
        )

    bars = ensure_bars(pd.concat(frames, ignore_index=True))
    meta_out = meta_from_bars(bars)
    return bars, meta_out
