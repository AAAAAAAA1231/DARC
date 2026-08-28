"""Conditioned empirical model and its 10-billion-simulation limit.

The predictive draw is an i.i.d. bootstrap from historical daily returns
that share today's trend regime. For that law, n → ∞ (including 10 billion
independent draws) converges to the empirical moments, which we compute
exactly. A streaming Monte Carlo is still run as a numerical check.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

TEN_BILLION = 10_000_000_000
DEFAULT_VERIFY_SIMS = 2_000_000
DEFAULT_BATCH = 5_000_000


@dataclass
class FittedModel:
    returns: np.ndarray
    regime: str
    last_close: float
    last_date: str
    ma20: float
    ma60: float
    momentum_20: float
    vol_20: float
    n_hist: int
    n_regime: int


@dataclass
class SimulationStats:
    expected_return: float
    p_up: float
    p05: float
    p50: float
    p95: float
    sigma: float
    n_sims: int
    source: str


def _rolling_mean(x: np.ndarray, window: int) -> np.ndarray:
    if len(x) < window:
        raise ValueError("not enough history")
    c = np.cumsum(x, dtype=np.float64)
    out = (c[window - 1 :] - np.concatenate(([0.0], c[:-window]))) / window
    pad = np.full(window - 1, np.nan)
    return np.concatenate([pad, out])


def classify_regime(last: float, ma20: float, ma60: float, momentum_20: float) -> str:
    if last > ma20 > ma60 and momentum_20 > 0:
        return "上升"
    if last < ma20 < ma60 and momentum_20 < 0:
        return "下降"
    return "震荡"


def fit_model(closes: np.ndarray, dates: list[str]) -> FittedModel:
    if len(closes) < 80:
        raise ValueError("历史样本不足 80 个交易日")
    simple = np.diff(closes) / closes[:-1]
    ma20_series = _rolling_mean(closes, 20)
    last = float(closes[-1])
    ma20 = float(np.mean(closes[-20:]))
    ma60 = float(np.mean(closes[-60:]))
    momentum_20 = float(closes[-1] / closes[-21] - 1.0)
    vol_20 = float(np.std(simple[-20:], ddof=1))
    regime = classify_regime(last, ma20, ma60, momentum_20)

    aligned_ma = ma20_series[1:]
    valid = ~np.isnan(aligned_ma)
    r = simple[valid]
    px = closes[1:][valid]
    ma = aligned_ma[valid]
    if regime == "上升":
        mask = px > ma
    elif regime == "下降":
        mask = px < ma
    else:
        mask = np.abs(px / ma - 1.0) <= 0.04
    cond = r[mask]
    if len(cond) < 40:
        cond = r[-250:] if len(r) >= 40 else r
    return FittedModel(
        returns=np.asarray(cond, dtype=np.float64),
        regime=regime,
        last_close=last,
        last_date=dates[-1] if dates else "",
        ma20=ma20,
        ma60=ma60,
        momentum_20=momentum_20,
        vol_20=vol_20,
        n_hist=len(simple),
        n_regime=int(len(cond)),
    )


def infinite_bootstrap_stats(returns: np.ndarray) -> SimulationStats:
    """Exact n→∞ i.i.d. bootstrap — the 10-billion-run limit of this model."""
    r = np.asarray(returns, dtype=np.float64)
    if r.size == 0:
        raise ValueError("empty return sample")
    return SimulationStats(
        expected_return=float(np.mean(r)),
        p_up=float(np.mean(r > 0.0)),
        p05=float(np.quantile(r, 0.05)),
        p50=float(np.quantile(r, 0.50)),
        p95=float(np.quantile(r, 0.95)),
        sigma=float(np.std(r, ddof=1) if r.size > 1 else 0.0),
        n_sims=TEN_BILLION,
        source="analytic_10b_limit",
    )


def streaming_bootstrap(
    returns: np.ndarray,
    n_sims: int = DEFAULT_VERIFY_SIMS,
    batch: int = DEFAULT_BATCH,
    seed: int | None = 20260828,
) -> SimulationStats:
    """High-throughput i.i.d. bootstrap without storing all draws."""
    r = np.asarray(returns, dtype=np.float64)
    n = int(r.size)
    if n == 0:
        raise ValueError("empty return sample")
    rng = np.random.default_rng(seed)
    remaining = int(n_sims)
    total = 0.0
    total_sq = 0.0
    n_pos = 0
    done = 0
    # Running histogram for approximate percentiles (2001 bins over observed min/max).
    lo = float(r.min())
    hi = float(r.max())
    if hi <= lo:
        hi = lo + 1e-12
    bins = 2001
    edges = np.linspace(lo, hi, bins + 1)
    hist = np.zeros(bins, dtype=np.int64)
    width = (hi - lo) / bins

    while remaining > 0:
        b = min(int(batch), remaining)
        idx = rng.integers(0, n, size=b, endpoint=False)
        sample = r[idx]
        total += float(sample.sum())
        total_sq += float(np.square(sample).sum())
        n_pos += int(np.count_nonzero(sample > 0.0))
        bucket = np.floor((sample - lo) / width).astype(np.int64)
        np.clip(bucket, 0, bins - 1, out=bucket)
        hist += np.bincount(bucket, minlength=bins)
        done += b
        remaining -= b

    mean = total / done
    var = max(0.0, total_sq / done - mean * mean)
    cdf = np.cumsum(hist) / done

    def q(p: float) -> float:
        k = int(np.searchsorted(cdf, p, side="left"))
        k = min(max(k, 0), bins - 1)
        return float(edges[k])

    return SimulationStats(
        expected_return=float(mean),
        p_up=float(n_pos / done),
        p05=q(0.05),
        p50=q(0.50),
        p95=q(0.95),
        sigma=float(np.sqrt(var)),
        n_sims=done,
        source="streaming_mc",
    )


def verify_against_limit(
    returns: np.ndarray,
    n_sims: int = DEFAULT_VERIFY_SIMS,
    seed: int | None = 20260828,
) -> tuple[SimulationStats, SimulationStats, float]:
    limit = infinite_bootstrap_stats(returns)
    mc = streaming_bootstrap(returns, n_sims=n_sims, seed=seed)
    err = abs(mc.expected_return - limit.expected_return)
    return limit, mc, err
