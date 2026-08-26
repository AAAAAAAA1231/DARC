"""Vectorized price indicators (no TA-Lib dependency)."""

from __future__ import annotations

import numpy as np
import pandas as pd


def ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False).mean()


def sma(s: pd.Series, window: int) -> pd.Series:
    return s.rolling(window, min_periods=max(2, window // 2)).mean()


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev = close.shift(1)
    return pd.concat([(high - low).abs(), (high - prev).abs(), (low - prev).abs()], axis=1).max(axis=1)


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    return true_range(high, low, close).ewm(span=window, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    up = delta.clip(lower=0.0)
    down = -delta.clip(upper=0.0)
    au = up.ewm(alpha=1.0 / window, adjust=False).mean()
    ad = down.ewm(alpha=1.0 / window, adjust=False).mean()
    rs = au / ad.replace(0.0, np.nan)
    return 100.0 - 100.0 / (1.0 + rs)


def roc(close: pd.Series, window: int = 20) -> pd.Series:
    return close.pct_change(window)


def zscore(close: pd.Series, window: int = 20) -> pd.Series:
    m = sma(close, window)
    sd = close.rolling(window, min_periods=max(2, window // 2)).std()
    return (close - m) / sd.replace(0.0, np.nan)


def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = true_range(high, low, close)
    atr_ = tr.ewm(span=window, adjust=False).mean()
    plus_di = 100.0 * pd.Series(plus_dm, index=close.index).ewm(span=window, adjust=False).mean() / atr_
    minus_di = 100.0 * pd.Series(minus_dm, index=close.index).ewm(span=window, adjust=False).mean() / atr_
    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(span=window, adjust=False).mean()


def realized_vol(close: pd.Series, window: int = 20) -> pd.Series:
    return close.pct_change().rolling(window, min_periods=max(5, window // 2)).std() * np.sqrt(252)


def tanh_clip(x: pd.Series | np.ndarray, scale: float = 1.0) -> pd.Series:
    arr = np.tanh(np.asarray(x, dtype=float) / max(scale, 1e-9))
    if isinstance(x, pd.Series):
        return pd.Series(arr, index=x.index)
    return pd.Series(arr)
