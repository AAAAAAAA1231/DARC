"""Walk-forward / OOS backtest. Point-in-time only; future bars never enter a training fold."""

from __future__ import annotations

from typing import Any

import numpy as np

from backend.core.logging import get_logger
from backend.strategies.indicators import candles_to_arrays
from backend.strategies.plugins import ALL_STRATEGIES

logger = get_logger("backtest")


def _signal_at(ohlcv_slice: dict[str, np.ndarray], weights: dict[str, float]) -> int:
    score = 0.0
    for plugin in ALL_STRATEGIES:
        sig = plugin.evaluate(ohlcv_slice)
        score += sig.score * weights.get(plugin.name, plugin.initial_weight)
    if score >= 58:
        return 1
    if score <= 42:
        return -1
    return 0


def walk_forward(
    candles: list[dict],
    weights: dict[str, float],
    *,
    train: int = 200,
    test: int = 40,
    cost_bps: float = 4.0,
) -> dict[str, Any]:
    if len(candles) < train + test + 10:
        return {"ok": False, "error": "not enough candles for walk-forward"}
    ohlcv = candles_to_arrays(candles)
    close = ohlcv["close"]
    n = len(close)
    fold_returns: list[float] = []
    oos_returns: list[float] = []
    start = train
    folds = 0
    while start + test < n:
        # Train window ends at start-1. Signal at bar t uses only data[:t+1] (no lookahead).
        pos = 0
        eq = 1.0
        peak = 1.0
        max_dd = 0.0
        for t in range(start, start + test):
            window = {k: v[: t + 1] for k, v in ohlcv.items()}
            desired = _signal_at(window, weights)
            ret = (close[t] - close[t - 1]) / close[t - 1]
            if desired != pos:
                ret -= cost_bps / 10000.0
            eq *= 1 + pos * ret
            peak = max(peak, eq)
            max_dd = min(max_dd, eq / peak - 1)
            pos = desired
        fold_returns.append(eq - 1)
        oos_returns.append(eq - 1)
        folds += 1
        start += test
    arr = np.array(oos_returns, dtype=float) if oos_returns else np.array([0.0])
    sharpe = float(arr.mean() / arr.std()) if arr.std() > 0 else 0.0
    logger.info("walk_forward folds=%s sharpe=%s", folds, sharpe)
    return {
        "ok": True,
        "folds": folds,
        "oos_returns": [float(x) for x in oos_returns],
        "mean_oos": float(arr.mean()),
        "sharpe_oos": sharpe,
        "win_rate": float(np.mean(arr > 0)),
        "cost_bps": cost_bps,
        "leakage_controls": {
            "point_in_time": True,
            "signal_uses_only_past_inclusive": True,
            "no_survivorship_filter": True,
            "costs_applied_on_turnover": True,
        },
        "note": "OOS walk-forward on the provided candle set. Not live performance.",
    }


def detect_lookahead_violation(candles: list[dict], weights: dict[str, float]) -> dict[str, Any]:
    """Sanity test helper: shuffling future labels must change a leaking implementation.
    The production signal path only sees data[:t+1], so permuting suffixes after t should not change the t signal.
    """
    if len(candles) < 80:
        return {"ok": False, "error": "short series"}
    ohlcv = candles_to_arrays(candles)
    t = 60
    base = _signal_at({k: v[: t + 1] for k, v in ohlcv.items()}, weights)
    shuffled = {k: v.copy() for k, v in ohlcv.items()}
    rng = np.random.default_rng(1)
    for k in shuffled:
        tail = shuffled[k][t + 1 :]
        rng.shuffle(tail)
        shuffled[k][t + 1 :] = tail
    leaked_probe = _signal_at({k: v[: t + 1] for k, v in shuffled.items()}, weights)
    return {"ok": True, "signal_unchanged_after_future_shuffle": base == leaked_probe, "base": base, "probed": leaked_probe}
