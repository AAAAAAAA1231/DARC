from __future__ import annotations

import numpy as np
import pandas as pd


def _s(x: np.ndarray) -> pd.Series:
    return pd.Series(np.asarray(x, dtype=float))


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return _s(x).rolling(n, min_periods=n).mean().to_numpy()


def ema(x: np.ndarray, n: int) -> np.ndarray:
    return _s(x).ewm(span=n, adjust=False, min_periods=n).mean().to_numpy()


def stdev(x: np.ndarray, n: int) -> np.ndarray:
    return _s(x).rolling(n, min_periods=n).std(ddof=0).to_numpy()


def rolling_max(x: np.ndarray, n: int) -> np.ndarray:
    return _s(x).rolling(n, min_periods=n).max().to_numpy()


def rolling_min(x: np.ndarray, n: int) -> np.ndarray:
    return _s(x).rolling(n, min_periods=n).min().to_numpy()


def true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    prev = np.concatenate([[close[0]], close[:-1]])
    return np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    return _s(true_range(high, low, close)).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()


def rsi(close: np.ndarray, n: int = 14) -> np.ndarray:
    delta = _s(close).diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    avg_loss = loss.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()
    rsi_val = np.where(
        avg_loss.to_numpy() == 0,
        np.where(avg_gain.to_numpy() == 0, 50.0, 100.0),
        100.0 - (100.0 / (1.0 + avg_gain.to_numpy() / np.where(avg_loss.to_numpy() == 0, np.nan, avg_loss.to_numpy()))),
    )
    return rsi_val


def macd(close: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    dif = ema(close, fast) - ema(close, slow)
    dea = ema(dif, signal)
    hist = (dif - dea) * 2.0
    return dif, dea, hist


def kdj(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    lowest = rolling_min(low, n)
    highest = rolling_max(high, n)
    rsv = (close - lowest) / np.where(highest - lowest == 0, np.nan, highest - lowest) * 100.0
    k = _s(rsv).ewm(alpha=1 / 3, adjust=False, min_periods=n).mean().to_numpy()
    d = _s(k).ewm(alpha=1 / 3, adjust=False, min_periods=n).mean().to_numpy()
    j = 3.0 * k - 2.0 * d
    return k, d, j


def bollinger(close: np.ndarray, n: int = 20, k: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    mid = sma(close, n)
    sd = stdev(close, n)
    upper = mid + k * sd
    lower = mid - k * sd
    width = (upper - lower) / np.where(mid == 0, np.nan, mid)
    return mid, upper, lower, width


def cci(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    tp = (high + low + close) / 3.0
    ma = sma(tp, n)
    md = _s(np.abs(tp - ma)).rolling(n, min_periods=n).mean().to_numpy()
    return (tp - ma) / np.where(md == 0, np.nan, 0.015 * md)


def williams_r(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    hh = rolling_max(high, n)
    ll = rolling_min(low, n)
    return (hh - close) / np.where(hh - ll == 0, np.nan, hh - ll) * -100.0


def bias(close: np.ndarray, n: int = 6) -> np.ndarray:
    ma = sma(close, n)
    return (close - ma) / np.where(ma == 0, np.nan, ma) * 100.0


def psy(close: np.ndarray, n: int = 12) -> np.ndarray:
    up = (_s(close).diff() > 0).astype(float)
    return up.rolling(n, min_periods=n).mean().to_numpy() * 100.0


def roc(close: np.ndarray, n: int = 12) -> np.ndarray:
    prev = _s(close).shift(n).to_numpy()
    return (close - prev) / np.where(prev == 0, np.nan, prev) * 100.0


def obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    direction = np.sign(np.diff(close, prepend=close[0]))
    return np.cumsum(direction * volume)


def mfi(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, n: int = 14) -> np.ndarray:
    tp = (high + low + close) / 3.0
    mf = tp * volume
    delta = np.diff(tp, prepend=tp[0])
    pos = np.where(delta > 0, mf, 0.0)
    neg = np.where(delta < 0, mf, 0.0)
    pos_n = _s(pos).rolling(n, min_periods=n).sum()
    neg_n = _s(neg).rolling(n, min_periods=n).sum().replace(0.0, np.nan)
    ratio = pos_n / neg_n
    return (100.0 - (100.0 / (1.0 + ratio))).to_numpy()


def vr(close: np.ndarray, volume: np.ndarray, n: int = 26) -> np.ndarray:
    chg = _s(close).diff()
    avs = np.where(chg > 0, volume, 0.0)
    bvs = np.where(chg < 0, volume, 0.0)
    cvs = np.where(chg == 0, volume, 0.0)
    a = _s(avs).rolling(n, min_periods=n).sum()
    b = _s(bvs).rolling(n, min_periods=n).sum()
    c = _s(cvs).rolling(n, min_periods=n).sum()
    return ((a + c / 2.0) / (b + c / 2.0).replace(0.0, np.nan) * 100.0).to_numpy()


def dmi_adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    up_move = np.diff(high, prepend=high[0])
    down_move = -np.diff(low, prepend=low[0])
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    atr_n = atr(high, low, close, n)
    plus_di = 100.0 * _s(plus_dm).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy() / atr_n
    minus_di = 100.0 * _s(minus_dm).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy() / atr_n
    dx = 100.0 * np.abs(plus_di - minus_di) / np.where((plus_di + minus_di) == 0, np.nan, plus_di + minus_di)
    adx = _s(dx).ewm(alpha=1 / n, adjust=False, min_periods=n).mean().to_numpy()
    return plus_di, minus_di, adx


def trix(close: np.ndarray, n: int = 12) -> np.ndarray:
    t = ema(ema(ema(close, n), n), n)
    prev = _s(t).shift(1).to_numpy()
    return (t - prev) / np.where(prev == 0, np.nan, prev) * 100.0


def donchian(high: np.ndarray, low: np.ndarray, n: int = 20) -> tuple[np.ndarray, np.ndarray]:
    return rolling_max(high, n), rolling_min(low, n)


def keltner(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 20, k: float = 1.5) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mid = ema(close, n)
    band = atr(high, low, close, n) * k
    return mid, mid + band, mid - band


def typical_price(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    return (high + low + close) / 3.0


def vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray, n: int = 20) -> np.ndarray:
    tp = typical_price(high, low, close)
    pv = _s(tp * volume).rolling(n, min_periods=n).sum()
    vv = _s(volume).rolling(n, min_periods=n).sum().replace(0.0, np.nan)
    return (pv / vv).to_numpy()


def rolling_hv(close: np.ndarray, n: int = 20) -> np.ndarray:
    rets = _s(close).pct_change()
    return (rets.rolling(n, min_periods=n).std(ddof=0) * np.sqrt(242)).to_numpy()
