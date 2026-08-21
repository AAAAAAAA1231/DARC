from __future__ import annotations

from collections.abc import Callable
from typing import Iterable

import numpy as np

from web3_radar.config import INITIAL_INDICATOR_SHARES, MONTE_CARLO_SIMS

ProgressFn = Callable[[int, int], None]
ELITE_CAP = 80_000


def normalize_shares(shares: dict[str, float], names: Iterable[str]) -> np.ndarray:
    arr = np.array([max(float(shares.get(name, 1.0)), 1e-6) for name in names], dtype=np.float64)
    return arr / arr.sum()


def monte_carlo_reweight(
    names: list[str],
    expectancies: np.ndarray,
    initial_shares: dict[str, float] | None = None,
    n_sims: int = MONTE_CARLO_SIMS,
    top_pct: float = 1.0,
    concentration: float = 24.0,
    rng: np.random.Generator | None = None,
    on_progress: ProgressFn | None = None,
) -> dict[str, float]:
    """Sample n_sims Dirichlet weight vectors around the initial shares, score by
    expectancy, then return the score-weighted average of the elite set.
    """
    if initial_shares is None:
        initial_shares = INITIAL_INDICATOR_SHARES
    gen = rng or np.random.default_rng(42)
    base = normalize_shares(initial_shares, names)
    exp = np.asarray(expectancies, dtype=np.float64)
    if exp.shape != base.shape:
        raise ValueError("expectancies length must match indicator names")

    alpha = np.maximum(base * concentration, 1e-3)
    n_sims = max(int(n_sims), 1)
    k = max(1, int(np.ceil(n_sims * max(float(top_pct), 0.01) / 100.0)))
    k = min(k, ELITE_CAP)
    n_ind = len(base)
    cap = max(k * 2, k + 1)
    buf_w = np.empty((cap, n_ind), dtype=np.float64)
    buf_s = np.empty((cap,), dtype=np.float64)
    filled = 0

    if n_sims >= 100_000_000:
        batch = 400_000
    elif n_sims >= 1_000_000:
        batch = 200_000
    else:
        batch = min(n_sims, 50_000)
    report_every = max(batch, max(n_sims // 100, 1))
    remaining = n_sims
    finished = 0
    last_report = 0

    def prune(keep: int) -> None:
        nonlocal filled
        if filled <= keep:
            return
        idx = np.argpartition(buf_s[:filled], -keep)[-keep:]
        buf_w[:keep] = buf_w[idx]
        buf_s[:keep] = buf_s[idx]
        filled = keep

    while remaining > 0:
        orig = min(batch, remaining)
        remaining -= orig
        weights = gen.dirichlet(alpha, size=orig)
        scores = weights @ exp
        n = orig
        if n > k:
            idx = np.argpartition(scores, -k)[-k:]
            weights = weights[idx]
            scores = scores[idx]
            n = k
        if filled + n > cap:
            prune(k)
        take = min(n, cap - filled)
        buf_w[filled : filled + take] = weights[:take]
        buf_s[filled : filled + take] = scores[:take]
        filled += take
        if filled >= cap:
            prune(k)
        finished += orig
        if on_progress and (finished - last_report >= report_every or remaining == 0):
            on_progress(finished, n_sims)
            last_report = finished

    prune(k)
    if filled <= 0:
        blended = base
    else:
        top_w = buf_w[:filled]
        top_s = buf_s[:filled]
        shifted = top_s - top_s.min() + 1e-9
        blended = np.average(top_w, axis=0, weights=shifted)
        blended = blended / blended.sum()
    return {name: float(blended[i]) for i, name in enumerate(names)}


def composite_score(signals: np.ndarray, strengths: np.ndarray, weights: np.ndarray) -> float:
    signed = signals.astype(np.float64) * np.clip(strengths.astype(np.float64), 0, 1)
    return float(np.dot(weights, signed))


def decision_from_score(score: float, threshold: float = 0.18) -> str:
    if score >= threshold:
        return "涨"
    if score <= -threshold:
        return "跌"
    return "观望"
