"""ATR / volatility adaptive take-profit and stop-loss bands."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import RiskConfig
from ..indicators import atr, realized_vol


def adaptive_k(close: pd.Series, cfg: RiskConfig) -> tuple[float, float]:
    if not cfg.vol_adapt or len(close) < 30:
        return cfg.stop_atr_k, cfg.take_atr_k
    rv = realized_vol(close, 20).iloc[-1]
    med = realized_vol(close, 20).median()
    if not np.isfinite(rv) or not np.isfinite(med) or med <= 0:
        return cfg.stop_atr_k, cfg.take_atr_k
    ratio = float(np.clip(rv / med, 0.6, 1.8))
    # High-vol: widen stops, modestly widen targets (avoid noise stop-outs).
    stop_k = cfg.stop_atr_k * (0.75 + 0.4 * ratio)
    take_k = cfg.take_atr_k * (0.85 + 0.25 * ratio)
    return float(stop_k), float(take_k)


def atr_bands(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    cfg: RiskConfig,
    entry: float | None = None,
) -> dict[str, float]:
    window = cfg.atr_window
    a = float(atr(high, low, close, window).iloc[-1])
    px = float(close.iloc[-1] if entry is None else entry)
    if not np.isfinite(a) or a <= 0:
        a = px * 0.02
    stop_k, take_k = adaptive_k(close, cfg)
    stop = round(max(0.01, px - stop_k * a), 2)
    take = round(px + take_k * a, 2)
    return {
        "atr": a,
        "atr_pct": a / px if px else np.nan,
        "stop_k": stop_k,
        "take_k": take_k,
        "stop_loss": stop,
        "take_profit": take,
        "entry_ref": px,
        "stop_distance_pct": (px - stop) / px if px else np.nan,
        "take_distance_pct": (take - px) / px if px else np.nan,
    }
