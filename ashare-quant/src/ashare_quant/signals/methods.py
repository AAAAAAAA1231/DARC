"""Five complementary signal families, each mapped to [-1, 1]."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .. import indicators as ta
from ..config import AppConfig, SignalName


def _prep(bars: pd.DataFrame) -> pd.DataFrame:
    g = bars.sort_values("date").copy()
    g["ret"] = g["close"].pct_change()
    return g


def trend_signal(bars: pd.DataFrame, params: dict) -> pd.Series:
    g = _prep(bars)
    fast = ta.ema(g["close"], int(params.get("fast", 12)))
    slow = ta.ema(g["close"], int(params.get("slow", 48)))
    adx = ta.adx(g["high"], g["low"], g["close"], int(params.get("adx_window", 14)))
    gap = (fast - slow) / slow.replace(0.0, np.nan)
    strength = (adx.fillna(0) / 40.0).clip(0.3, 1.5)
    score = ta.tanh_clip(gap * 8.0) * strength.clip(upper=1.0)
    return score.clip(-1, 1)


def momentum_signal(bars: pd.DataFrame, params: dict) -> pd.Series:
    g = _prep(bars)
    roc = ta.roc(g["close"], int(params.get("roc_window", 20)))
    rsi = ta.rsi(g["close"], int(params.get("rsi_window", 14)))
    roc_s = ta.tanh_clip(roc * 6.0)
    rsi_s = ((rsi - 50.0) / 50.0).clip(-1, 1)
    return (0.7 * roc_s + 0.3 * rsi_s).clip(-1, 1)


def mean_reversion_signal(bars: pd.DataFrame, params: dict) -> pd.Series:
    g = _prep(bars)
    z = ta.zscore(g["close"], int(params.get("z_window", 20)))
    entry = float(params.get("entry_z", 1.2))
    # Fade stretched moves; near zero z stays quiet.
    raw = -z / max(entry, 1e-6)
    return ta.tanh_clip(raw, 1.0).clip(-1, 1)


def volatility_signal(bars: pd.DataFrame, params: dict) -> pd.Series:
    """ATR breakout (trend-following in expanding vol) vs contraction fade."""
    g = _prep(bars)
    window = int(params.get("atr_window", 14))
    k = float(params.get("breakout_k", 1.8))
    atr_ = ta.atr(g["high"], g["low"], g["close"], window)
    mid = ta.sma(g["close"], window)
    upper = mid + k * atr_
    lower = mid - k * atr_
    breakout = np.where(g["close"] > upper, 1.0, np.where(g["close"] < lower, -1.0, 0.0))
    rv = ta.realized_vol(g["close"], window)
    rv_z = (rv - rv.rolling(60, min_periods=20).mean()) / rv.rolling(60, min_periods=20).std()
    squeeze = (-ta.tanh_clip(rv_z.fillna(0.0), 1.5)) * 0.25
    return (pd.Series(breakout, index=g.index) * 0.85 + squeeze).clip(-1, 1)


def relative_strength_signal(bars: pd.DataFrame, params: dict, bench: pd.Series | None = None) -> pd.Series:
    g = _prep(bars)
    window = int(params.get("window", 20))
    stock = ta.roc(g["close"], window)
    if bench is not None:
        b = pd.Series(bench.values, index=g.index[: len(bench)])
        bench_s = b.pct_change(window)
    elif "benchmark_close" in g.columns:
        bench_s = ta.roc(g["benchmark_close"], window)
    else:
        bench_s = 0.0
    rs = stock - bench_s
    return ta.tanh_clip(rs * 8.0).clip(-1, 1)


_BUILDERS = {
    SignalName.TREND: lambda b, p, _idx: trend_signal(b, p),
    SignalName.MOMENTUM: lambda b, p, _idx: momentum_signal(b, p),
    SignalName.MEAN_REVERSION: lambda b, p, _idx: mean_reversion_signal(b, p),
    SignalName.VOLATILITY: lambda b, p, _idx: volatility_signal(b, p),
    SignalName.RELATIVE_STRENGTH: lambda b, p, idx: relative_strength_signal(b, p),
}


def method_scores(bars: pd.DataFrame, cfg: AppConfig, params: dict | None = None) -> pd.DataFrame:
    params = params or {}
    g = bars.sort_values("date").reset_index(drop=True)
    out = pd.DataFrame({"date": g["date"], "symbol": g["symbol"]})
    for name in cfg.ensemble.methods:
        p = {**getattr(cfg.signals, name.value), **params.get(name.value, {})}
        builder = _BUILDERS[name]
        s = builder(g, p, None)
        out[name.value] = pd.Series(s.values, index=out.index).astype(float).fillna(0.0).clip(-1, 1)
    return out


def last_method_scores(bars: pd.DataFrame, cfg: AppConfig, params: dict | None = None) -> dict[str, float]:
    frame = method_scores(bars, cfg, params)
    if frame.empty:
        return {m.value: 0.0 for m in cfg.ensemble.methods}
    row = frame.iloc[-1]
    return {m.value: float(row[m.value]) for m in cfg.ensemble.methods}
