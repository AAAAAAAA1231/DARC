"""Technical indicators used by strategy plugins. Pure functions on numpy arrays."""

from __future__ import annotations

import numpy as np


def ema(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) == 0:
        return values
    alpha = 2.0 / (period + 1)
    out = np.empty_like(values, dtype=float)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1 - alpha) * out[i - 1]
    return out


def sma(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) < period:
        return np.full_like(values, np.nan, dtype=float)
    kernel = np.ones(period) / period
    conv = np.convolve(values, kernel, mode="valid")
    pad = np.full(period - 1, np.nan)
    return np.concatenate([pad, conv])


def rsi(closes: np.ndarray, period: int = 14) -> np.ndarray:
    if len(closes) < period + 1:
        return np.full_like(closes, np.nan, dtype=float)
    delta = np.diff(closes, prepend=closes[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = ema(gain, period)
    avg_loss = ema(loss, period)
    rs = np.divide(avg_gain, avg_loss, out=np.zeros_like(avg_gain), where=avg_loss != 0)
    return 100 - (100 / (1 + rs))


def macd(closes: np.ndarray, fast: int = 12, slow: int = 26, signal: int = 9) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    line = ema(closes, fast) - ema(closes, slow)
    sig = ema(line, signal)
    hist = line - sig
    return line, sig, hist


def atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    prev = np.roll(close, 1)
    prev[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev), np.abs(low - prev)))
    return ema(tr, period)


def adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    up = high - np.roll(high, 1)
    down = np.roll(low, 1) - low
    up[0] = 0
    down[0] = 0
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr_atr = atr(high, low, close, period)
    plus_di = 100 * np.divide(ema(plus_dm, period), tr_atr, out=np.zeros_like(tr_atr), where=tr_atr != 0)
    minus_di = 100 * np.divide(ema(minus_dm, period), tr_atr, out=np.zeros_like(tr_atr), where=tr_atr != 0)
    dx = 100 * np.abs(plus_di - minus_di) / np.clip(plus_di + minus_di, 1e-9, None)
    return ema(dx, period)


def obv(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    direction = np.sign(np.diff(close, prepend=close[0]))
    return np.cumsum(direction * volume)


def vwap(high: np.ndarray, low: np.ndarray, close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    typical = (high + low + close) / 3.0
    cum_vol = np.cumsum(volume)
    return np.divide(np.cumsum(typical * volume), cum_vol, out=np.full_like(typical, np.nan), where=cum_vol != 0)


def swing_points(values: np.ndarray, left: int = 3, right: int = 3) -> tuple[list[int], list[int]]:
    highs: list[int] = []
    lows: list[int] = []
    n = len(values)
    for i in range(left, n - right):
        window = values[i - left : i + right + 1]
        if values[i] == window.max() and np.argmax(window) == left:
            highs.append(i)
        if values[i] == window.min() and np.argmin(window) == left:
            lows.append(i)
    return highs, lows


def candles_to_arrays(candles: list[dict]) -> dict[str, np.ndarray]:
    return {
        "open": np.array([float(c["open"]) for c in candles], dtype=float),
        "high": np.array([float(c["high"]) for c in candles], dtype=float),
        "low": np.array([float(c["low"]) for c in candles], dtype=float),
        "close": np.array([float(c["close"]) for c in candles], dtype=float),
        "volume": np.array([float(c["volume"]) for c in candles], dtype=float),
    }
