from __future__ import annotations

from typing import Iterable

import numpy as np

from web3_radar.config import INITIAL_INDICATOR_SHARES


def normalize_shares(shares: dict[str, float], names: Iterable[str]) -> np.ndarray:
    arr = np.array([max(float(shares.get(name, 1.0)), 1e-6) for name in names], dtype=np.float64)
    return arr / arr.sum()


def monte_carlo_reweight(
    names: list[str],
    expectancies: np.ndarray,
    initial_shares: dict[str, float] | None = None,
    n_sims: int = 1_000_000,
    top_pct: float = 1.0,
    concentration: float = 24.0,
    rng: np.random.Generator | None = None,
) -> dict[str, float]:
    """Sample n_sims Dirichlet weight vectors around the initial shares, score by
    expectancy, then return the score-weighted average of the top percentile.
    """
    if initial_shares is None:
        initial_shares = INITIAL_INDICATOR_SHARES
    gen = rng or np.random.default_rng(42)
    base = normalize_shares(initial_shares, names)
    exp = np.asarray(expectancies, dtype=np.float64)
    if exp.shape != base.shape:
        raise ValueError("expectancies length must match indicator names")

    alpha = np.maximum(base * concentration, 1e-3)
    n_sims = int(n_sims)
    k = max(1, int(np.ceil(n_sims * max(top_pct, 0.01) / 100.0)))
    best_w = np.empty((0, len(base)), dtype=np.float64)
    best_s = np.empty((0,), dtype=np.float64)
    remaining = n_sims
    batch = 100_000 if n_sims >= 100_000 else n_sims
    while remaining > 0:
        n = min(batch, remaining)
        remaining -= n
        weights = gen.dirichlet(alpha, size=n)
        scores = weights @ exp
        best_w = np.vstack((best_w, weights))
        best_s = np.concatenate((best_s, scores))
        if len(best_s) > k * 3 and remaining:
            idx = np.argpartition(best_s, -k)[-k:]
            best_w = best_w[idx]
            best_s = best_s[idx]
    idx = np.argpartition(best_s, -k)[-k:]
    top_w = best_w[idx]
    top_s = best_s[idx]
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
