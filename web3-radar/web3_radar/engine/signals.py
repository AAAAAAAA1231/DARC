from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from web3_radar.config import INITIAL_INDICATOR_SHARES
from web3_radar.engine.indicators import (
    compute_all_indicators,
    historical_expectancy,
    last_atr,
)
from web3_radar.engine.monte_carlo import (
    composite_score,
    decision_from_score,
    monte_carlo_reweight,
    normalize_shares,
)


def analyze_klines(
    df: pd.DataFrame,
    symbol: str,
    n_sims: int = 1_000_000,
    threshold: float = 0.18,
    atr_sl_mult: float = 1.5,
    atr_tp_mult: float = 2.5,
    initial_shares: dict[str, float] | None = None,
    top_pct: float = 1.0,
) -> dict[str, Any]:
    if df is None or len(df) < 60:
        raise ValueError("K 线数据不足，至少需要 60 根")
    shares = initial_shares or INITIAL_INDICATOR_SHARES
    indicators = compute_all_indicators(df)
    names = [i.name for i in indicators]
    expect_map = historical_expectancy(df)
    expectancies = np.array([expect_map.get(n, 0.0) for n in names], dtype=np.float64)
    # If history is flat, fall back to initial shares as prior
    if np.allclose(expectancies, 0):
        expectancies = normalize_shares(shares, names) * 0.01

    weights_map = monte_carlo_reweight(
        names,
        expectancies,
        initial_shares=shares,
        n_sims=n_sims,
        top_pct=top_pct,
    )
    weights = np.array([weights_map[n] for n in names], dtype=np.float64)
    signals = np.array([i.signal for i in indicators], dtype=np.float64)
    strengths = np.array([i.strength for i in indicators], dtype=np.float64)
    score = composite_score(signals, strengths, weights)
    decision = decision_from_score(score, threshold)
    price = float(df["close"].iloc[-1])
    atr_v = last_atr(df)
    if not math.isfinite(atr_v) or atr_v <= 0:
        atr_v = price * 0.02

    if decision == "涨":
        entry, sl, tp = price, price - atr_sl_mult * atr_v, price + atr_tp_mult * atr_v
        side = "long"
    elif decision == "跌":
        entry, sl, tp = price, price + atr_sl_mult * atr_v, price - atr_tp_mult * atr_v
        side = "short"
    else:
        entry, sl, tp = price, price - atr_sl_mult * atr_v, price + atr_tp_mult * atr_v
        side = "flat"

    return {
        "symbol": symbol,
        "decision": decision,
        "side": side,
        "score": round(score, 4),
        "confidence": round(min(1.0, abs(score) / max(threshold, 1e-6)), 4),
        "price": price,
        "entry": round(entry, 8),
        "stop_loss": round(sl, 8),
        "take_profit": round(tp, 8),
        "atr": round(atr_v, 8),
        "n_sims": int(n_sims),
        "weights_adjusted": True,
        "sim_note": f"已按初始份额完成 {int(n_sims):,} 次蒙特卡洛模拟，并对指标权重做加权平均修正",
        "indicators": [
            {
                "name": i.name,
                "signal": i.signal,
                "strength": round(i.strength, 4),
                "detail": i.detail,
                "expectancy": round(float(expect_map.get(i.name, 0.0)), 6),
                "weight_initial": round(float(shares.get(i.name, 1.0)), 4),
                "weight_optimized": round(weights_map[i.name], 4),
            }
            for i in indicators
        ],
    }
