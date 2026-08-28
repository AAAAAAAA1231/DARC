from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from market_advisor.markets import MARKETS, Market
from market_advisor.quotes import BarSeries


def synthetic_closes(n: int = 260, start: float = 3000.0, drift: float = 0.0004, seed: int = 1) -> np.ndarray:
    rng = np.random.default_rng(seed)
    shocks = rng.normal(drift, 0.012, size=n - 1)
    logp = np.concatenate([[np.log(start)], np.log(start) + np.cumsum(shocks)])
    return np.exp(logp)


def synthetic_dates(n: int = 260) -> list[str]:
    day = date(2025, 8, 1)
    out: list[str] = []
    while len(out) < n:
        if day.weekday() < 5:
            out.append(day.isoformat())
        day += timedelta(days=1)
    return out


def fake_series(market: Market | None = None, drift: float = 0.0006, seed: int = 7) -> BarSeries:
    market = market or MARKETS[0]
    closes = synthetic_closes(seed=seed, drift=drift)
    dates = synthetic_dates(len(closes))
    return BarSeries(
        market=market,
        name=market.name + "指数",
        dates=dates,
        closes=closes,
        spot=float(closes[-1] * 1.002),
        change_pct=0.20,
        fetched_at="2026-08-28T09:30:00",
        source="test",
    )
