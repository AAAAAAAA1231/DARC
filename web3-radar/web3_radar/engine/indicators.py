from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np
import pandas as pd


@dataclass
class IndicatorResult:
    name: str
    signal: int  # -1 跌, 0 观望, 1 涨
    strength: float  # 0-1
    detail: str
    expectancy: float = 0.0


def _series(df: pd.DataFrame, col: str) -> np.ndarray:
    return df[col].to_numpy(dtype=np.float64)


def atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    high = _series(df, "high")
    low = _series(df, "low")
    close = _series(df, "close")
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    out = np.zeros_like(tr)
    if len(tr) < period:
        out[:] = np.nanmean(tr)
        return out
    out[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, len(tr)):
        out[i] = out[i - 1] * (1 - alpha) + tr[i] * alpha
    out[: period - 1] = out[period - 1]
    return out


def ema(values: np.ndarray, period: int) -> np.ndarray:
    out = np.empty_like(values)
    if len(values) == 0:
        return out
    k = 2.0 / (period + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def sma(values: np.ndarray, period: int) -> np.ndarray:
    if len(values) < period:
        return np.full_like(values, np.nanmean(values) if len(values) else np.nan)
    csum = np.cumsum(values)
    out = np.empty_like(values)
    out[: period - 1] = np.nan
    out[period - 1 :] = (csum[period - 1 :] - np.concatenate(([0], csum[:-period]))) / period
    valid = out[period - 1]
    out[: period - 1] = valid
    return out


def rsi(values: np.ndarray, period: int = 14) -> np.ndarray:
    delta = np.diff(values, prepend=values[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    avg_gain = ema(gain, period)
    avg_loss = ema(loss, period)
    rs = np.divide(avg_gain, np.maximum(avg_loss, 1e-12))
    return 100 - (100 / (1 + rs))


def macd(values: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    line = ema(values, 12) - ema(values, 26)
    signal = ema(line, 9)
    hist = line - signal
    return line, signal, hist


def bollinger(values: np.ndarray, period: int = 20, nstd: float = 2.0) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mid = sma(values, period)
    std = pd.Series(values).rolling(period, min_periods=1).std().to_numpy()
    return mid + nstd * std, mid, mid - nstd * std


def stochastic(df: pd.DataFrame, k_period: int = 14, d_period: int = 3) -> tuple[np.ndarray, np.ndarray]:
    low_n = df["low"].rolling(k_period, min_periods=1).min().to_numpy()
    high_n = df["high"].rolling(k_period, min_periods=1).max().to_numpy()
    close = _series(df, "close")
    k = 100 * (close - low_n) / np.maximum(high_n - low_n, 1e-12)
    d = sma(k, d_period)
    return k, d


def williams_r(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    low_n = df["low"].rolling(period, min_periods=1).min().to_numpy()
    high_n = df["high"].rolling(period, min_periods=1).max().to_numpy()
    close = _series(df, "close")
    return -100 * (high_n - close) / np.maximum(high_n - low_n, 1e-12)


def cci(df: pd.DataFrame, period: int = 20) -> np.ndarray:
    tp = (df["high"] + df["low"] + df["close"]) / 3
    sma_tp = tp.rolling(period, min_periods=1).mean()
    mad = (tp - sma_tp).abs().rolling(period, min_periods=1).mean()
    return ((tp - sma_tp) / (0.015 * mad.replace(0, np.nan))).fillna(0).to_numpy()


def mfi(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    tp = ((df["high"] + df["low"] + df["close"]) / 3).to_numpy()
    mf = tp * _series(df, "volume")
    delta = np.diff(tp, prepend=tp[0])
    pos = np.where(delta > 0, mf, 0.0)
    neg = np.where(delta < 0, mf, 0.0)
    pos_sum = pd.Series(pos).rolling(period, min_periods=1).sum().to_numpy()
    neg_sum = pd.Series(neg).rolling(period, min_periods=1).sum().to_numpy()
    ratio = pos_sum / np.maximum(neg_sum, 1e-12)
    return 100 - (100 / (1 + ratio))


def obv(df: pd.DataFrame) -> np.ndarray:
    close = _series(df, "close")
    vol = _series(df, "volume")
    direction = np.sign(np.diff(close, prepend=close[0]))
    return np.cumsum(direction * vol)


def cmf(df: pd.DataFrame, period: int = 20) -> np.ndarray:
    high = _series(df, "high")
    low = _series(df, "low")
    close = _series(df, "close")
    vol = _series(df, "volume")
    mfm = ((close - low) - (high - close)) / np.maximum(high - low, 1e-12)
    mfv = mfm * vol
    return pd.Series(mfv).rolling(period, min_periods=1).sum().to_numpy() / np.maximum(
        pd.Series(vol).rolling(period, min_periods=1).sum().to_numpy(), 1e-12
    )


def parabolic_sar(df: pd.DataFrame, step: float = 0.02, max_af: float = 0.2) -> np.ndarray:
    high = _series(df, "high")
    low = _series(df, "low")
    n = len(df)
    sar = np.zeros(n)
    if n == 0:
        return sar
    bull = True
    af = step
    ep = high[0]
    sar[0] = low[0]
    for i in range(1, n):
        sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
        if bull:
            if low[i] < sar[i]:
                bull = False
                sar[i] = ep
                ep = low[i]
                af = step
            else:
                if high[i] > ep:
                    ep = high[i]
                    af = min(max_af, af + step)
        else:
            if high[i] > sar[i]:
                bull = True
                sar[i] = ep
                ep = high[i]
                af = step
            else:
                if low[i] < ep:
                    ep = low[i]
                    af = min(max_af, af + step)
    return sar


def supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> tuple[np.ndarray, np.ndarray]:
    hl2 = (_series(df, "high") + _series(df, "low")) / 2
    atr_v = atr(df, period)
    upper = hl2 + multiplier * atr_v
    lower = hl2 - multiplier * atr_v
    close = _series(df, "close")
    n = len(df)
    st = np.zeros(n)
    direction = np.ones(n)
    st[0] = upper[0]
    for i in range(1, n):
        if close[i] > st[i - 1]:
            direction[i] = 1
        elif close[i] < st[i - 1]:
            direction[i] = -1
        else:
            direction[i] = direction[i - 1]
        if direction[i] == 1:
            lower[i] = max(lower[i], lower[i - 1]) if direction[i - 1] == 1 else lower[i]
            st[i] = lower[i]
        else:
            upper[i] = min(upper[i], upper[i - 1]) if direction[i - 1] == -1 else upper[i]
            st[i] = upper[i]
    return st, direction


def adx_dmi(df: pd.DataFrame, period: int = 14) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    high = _series(df, "high")
    low = _series(df, "low")
    up = np.diff(high, prepend=high[0])
    down = -np.diff(low, prepend=low[0])
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    atr_v = np.maximum(atr(df, period), 1e-12)
    plus_di = 100 * ema(plus_dm, period) / atr_v
    minus_di = 100 * ema(minus_dm, period) / atr_v
    dx = 100 * np.abs(plus_di - minus_di) / np.maximum(plus_di + minus_di, 1e-12)
    return ema(dx, period), plus_di, minus_di


def ichimoku(df: pd.DataFrame) -> dict[str, np.ndarray]:
    high9 = df["high"].rolling(9, min_periods=1).max()
    low9 = df["low"].rolling(9, min_periods=1).min()
    high26 = df["high"].rolling(26, min_periods=1).max()
    low26 = df["low"].rolling(26, min_periods=1).min()
    high52 = df["high"].rolling(52, min_periods=1).max()
    low52 = df["low"].rolling(52, min_periods=1).min()
    tenkan = ((high9 + low9) / 2).to_numpy()
    kijun = ((high26 + low26) / 2).to_numpy()
    span_a = (tenkan + kijun) / 2
    span_b = ((high52 + low52) / 2).to_numpy()
    return {"tenkan": tenkan, "kijun": kijun, "span_a": span_a, "span_b": span_b}


def roc(values: np.ndarray, period: int = 12) -> np.ndarray:
    prev = np.roll(values, period)
    prev[:period] = values[:period]
    return (values - prev) / np.maximum(np.abs(prev), 1e-12) * 100


def trix(values: np.ndarray, period: int = 15) -> np.ndarray:
    t = ema(ema(ema(values, period), period), period)
    prev = np.roll(t, 1)
    prev[0] = t[0]
    return (t - prev) / np.maximum(np.abs(prev), 1e-12) * 100


def vwap(df: pd.DataFrame) -> np.ndarray:
    tp = (_series(df, "high") + _series(df, "low") + _series(df, "close")) / 3
    vol = _series(df, "volume")
    return np.cumsum(tp * vol) / np.maximum(np.cumsum(vol), 1e-12)


def awesome_oscillator(df: pd.DataFrame) -> np.ndarray:
    mid = (_series(df, "high") + _series(df, "low")) / 2
    return sma(mid, 5) - sma(mid, 34)


def ultimate_oscillator(df: pd.DataFrame) -> np.ndarray:
    close = _series(df, "close")
    high = _series(df, "high")
    low = _series(df, "low")
    prev = np.roll(close, 1)
    prev[0] = close[0]
    bp = close - np.minimum(low, prev)
    tr = np.maximum(high, prev) - np.minimum(low, prev)
    def avg(period: int) -> np.ndarray:
        return pd.Series(bp).rolling(period, min_periods=1).sum().to_numpy() / np.maximum(
            pd.Series(tr).rolling(period, min_periods=1).sum().to_numpy(), 1e-12
        )
    return 100 * (4 * avg(7) + 2 * avg(14) + avg(28)) / 7


def heikin_ashi(df: pd.DataFrame) -> pd.DataFrame:
    ha = pd.DataFrame(index=df.index)
    ha["close"] = (df["open"] + df["high"] + df["low"] + df["close"]) / 4
    ha_open = np.zeros(len(df))
    opens = df["open"].to_numpy()
    closes = ha["close"].to_numpy()
    ha_open[0] = (opens[0] + df["close"].iloc[0]) / 2
    for i in range(1, len(df)):
        ha_open[i] = (ha_open[i - 1] + closes[i - 1]) / 2
    ha["open"] = ha_open
    return ha


def zigzag_pivots(df: pd.DataFrame, pct: float = 0.03) -> list[tuple[int, float, int]]:
    """Return list of (index, price, 1=high/-1=low)."""
    highs = _series(df, "high")
    lows = _series(df, "low")
    if len(df) < 5:
        return []
    pivots: list[tuple[int, float, int]] = []
    last_pivot_price = (highs[0] + lows[0]) / 2
    last_dir = 0
    extreme_idx = 0
    extreme_price = last_pivot_price
    for i in range(1, len(df)):
        if last_dir >= 0:
            if highs[i] > extreme_price:
                extreme_price = highs[i]
                extreme_idx = i
            elif (extreme_price - lows[i]) / max(extreme_price, 1e-12) >= pct:
                pivots.append((extreme_idx, extreme_price, 1))
                last_dir = -1
                extreme_idx = i
                extreme_price = lows[i]
        if last_dir <= 0:
            if lows[i] < extreme_price:
                extreme_price = lows[i]
                extreme_idx = i
            elif (highs[i] - extreme_price) / max(extreme_price, 1e-12) >= pct:
                pivots.append((extreme_idx, extreme_price, -1))
                last_dir = 1
                extreme_idx = i
                extreme_price = highs[i]
    return pivots


def _near(value: float, target: float, tol: float = 0.08) -> bool:
    return abs(value - target) <= tol


def detect_harmonic(df: pd.DataFrame) -> IndicatorResult:
    pivots = zigzag_pivots(df, pct=0.025)
    if len(pivots) < 5:
        return IndicatorResult("harmonic", 0, 0.0, "枢轴点不足，无法识别谐波形态")
    x_i, x, _ = pivots[-5]
    a_i, a, _ = pivots[-4]
    b_i, b, _ = pivots[-3]
    c_i, c, _ = pivots[-2]
    d_i, d, _ = pivots[-1]
    xa = a - x
    if abs(xa) < 1e-12:
        return IndicatorResult("harmonic", 0, 0.0, "XA 过小")
    ab_xa = abs((b - a) / xa)
    ad_xa = abs((d - a) / xa) if abs(a - x) else 0
    bc_ab = abs((c - b) / (b - a)) if abs(b - a) > 1e-12 else 0
    cd_bc = abs((d - c) / (c - b)) if abs(c - b) > 1e-12 else 0
    bullish = d < c  # potential long at D of bullish pattern (D is low)
    patterns = []
    if _near(ab_xa, 0.618) and 0.382 <= bc_ab <= 0.886 and _near(ad_xa, 0.786, 0.1):
        patterns.append("Gartley")
    if 0.382 <= ab_xa <= 0.5 and 0.382 <= bc_ab <= 0.886 and _near(ad_xa, 0.886, 0.1):
        patterns.append("Bat")
    if _near(ab_xa, 0.786) and 1.27 <= abs((d - a) / xa) <= 2.24:
        patterns.append("Butterfly")
    if 0.382 <= ab_xa <= 0.618 and _near(abs((d - a) / xa), 1.618, 0.15):
        patterns.append("Crab")
    if 0.382 <= ab_xa <= 0.618 and 1.13 <= abs((c - a) / xa) <= 1.414 and _near(abs((d - c) / (c - x)) if abs(c - x) else 0, 0.786, 0.12):
        patterns.append("Cypher")
    if 0.446 <= ab_xa <= 0.618 and 1.13 <= bc_ab <= 1.618 and 1.618 <= cd_bc <= 2.24:
        patterns.append("Shark")
    if 0.382 <= ab_xa <= 0.886 and 1.13 <= cd_bc <= 2.618:
        patterns.append("ABCD")
    if not patterns:
        return IndicatorResult("harmonic", 0, 0.2, "未形成标准谐波，观望")
    name = "+".join(patterns[:2])
    signal = 1 if bullish else -1
    strength = min(1.0, 0.55 + 0.1 * len(patterns))
    side = "看涨反转" if signal == 1 else "看跌反转"
    return IndicatorResult("harmonic", signal, strength, f"{name} {side} D={d:.6g} (bar {d_i})")


def td_sequential(df: pd.DataFrame) -> IndicatorResult:
    close = _series(df, "close")
    n = len(close)
    buy_setup = sell_setup = 0
    buy_cd = sell_cd = 0
    last_buy_setup = last_sell_setup = 0
    last_buy_cd = last_sell_cd = 0
    for i in range(4, n):
        if close[i] < close[i - 4]:
            buy_setup += 1
            sell_setup = 0
        elif close[i] > close[i - 4]:
            sell_setup += 1
            buy_setup = 0
        else:
            buy_setup = sell_setup = 0
        last_buy_setup = buy_setup
        last_sell_setup = sell_setup
        if buy_setup >= 9 and i >= 2 and close[i] <= close[i - 2]:
            buy_cd += 1
        if sell_setup >= 9 and i >= 2 and close[i] >= close[i - 2]:
            sell_cd += 1
        if buy_setup == 0:
            buy_cd = 0
        if sell_setup == 0:
            sell_cd = 0
        last_buy_cd = buy_cd
        last_sell_cd = sell_cd

    if last_buy_cd >= 13:
        return IndicatorResult("td13", 1, 1.0, f"TD 买入倒计时 {last_buy_cd}，低位耗尽")
    if last_sell_cd >= 13:
        return IndicatorResult("td13", -1, 1.0, f"TD 卖出倒计时 {last_sell_cd}，高位耗尽")
    if last_buy_setup >= 9:
        return IndicatorResult("td13", 1, 0.7, f"TD 买入结构 {last_buy_setup}")
    if last_sell_setup >= 9:
        return IndicatorResult("td13", -1, 0.7, f"TD 卖出结构 {last_sell_setup}")
    if last_buy_setup >= 6:
        return IndicatorResult("td13", 1, 0.35, f"TD 买入结构进行中 {last_buy_setup}")
    if last_sell_setup >= 6:
        return IndicatorResult("td13", -1, 0.35, f"TD 卖出结构进行中 {last_sell_setup}")
    return IndicatorResult("td13", 0, 0.1, f"TD 中性 (买{last_buy_setup}/卖{last_sell_setup})")


def detect_elliott(df: pd.DataFrame) -> IndicatorResult:
    pivots = zigzag_pivots(df, pct=0.02)
    if len(pivots) < 6:
        return IndicatorResult("elliott", 0, 0.0, "波浪枢轴不足")
    pts = [p[1] for p in pivots[-6:]]
    w1, w2, w3, w4, w5 = pts[1] - pts[0], pts[2] - pts[1], pts[3] - pts[2], pts[4] - pts[3], pts[5] - pts[4]
    impulse_up = w1 > 0 and w2 < 0 and w3 > 0 and w4 < 0 and w5 > 0 and abs(w3) >= abs(w1) * 0.8
    impulse_dn = w1 < 0 and w2 > 0 and w3 < 0 and w4 > 0 and w5 < 0 and abs(w3) >= abs(w1) * 0.8
    if impulse_up:
        return IndicatorResult("elliott", -1, 0.65, "疑似五浪上涨结束，警惕回撤")
    if impulse_dn:
        return IndicatorResult("elliott", 1, 0.65, "疑似五浪下跌结束，关注反弹")
    return IndicatorResult("elliott", 0, 0.15, "未确认完整推动浪")


def _sign_from_last(cond_up: bool, cond_down: bool, strength: float, name: str, detail: str) -> IndicatorResult:
    if cond_up and not cond_down:
        return IndicatorResult(name, 1, strength, detail)
    if cond_down and not cond_up:
        return IndicatorResult(name, -1, strength, detail)
    return IndicatorResult(name, 0, 0.15, detail)


def compute_all_indicators(df: pd.DataFrame) -> list[IndicatorResult]:
    close = _series(df, "close")
    high = _series(df, "high")
    low = _series(df, "low")
    results: list[IndicatorResult] = [
        td_sequential(df),
        detect_harmonic(df),
        detect_elliott(df),
    ]

    r = rsi(close)
    results.append(_sign_from_last(r[-1] < 30, r[-1] > 70, min(1.0, abs(r[-1] - 50) / 50), "rsi", f"RSI={r[-1]:.1f}"))

    macd_line, macd_sig, hist = macd(close)
    results.append(
        _sign_from_last(
            macd_line[-1] > macd_sig[-1] and hist[-1] > hist[-2],
            macd_line[-1] < macd_sig[-1] and hist[-1] < hist[-2],
            min(1.0, abs(hist[-1]) / (np.std(hist[-50:]) + 1e-12) / 2),
            "macd",
            f"MACD hist={hist[-1]:.6g}",
        )
    )

    upper, mid, lower = bollinger(close)
    bw = (upper[-1] - lower[-1]) / max(mid[-1], 1e-12)
    results.append(
        _sign_from_last(
            close[-1] < lower[-1],
            close[-1] > upper[-1],
            min(1.0, abs(close[-1] - mid[-1]) / max(upper[-1] - mid[-1], 1e-12)),
            "bollinger",
            f"布林位置 close vs mid, 带宽={bw:.3f}",
        )
    )

    e12, e26, e50, e200 = ema(close, 12), ema(close, 26), ema(close, 50), ema(close, 200)
    results.append(
        _sign_from_last(
            e12[-1] > e26[-1] and e50[-1] > e200[-1],
            e12[-1] < e26[-1] and e50[-1] < e200[-1],
            0.7 if (e12[-1] - e26[-1]) * (e50[-1] - e200[-1]) > 0 else 0.35,
            "ema_cross",
            "EMA12/26 与 EMA50/200 共振" if (e12[-1] - e26[-1]) * (e50[-1] - e200[-1]) > 0 else "均线方向不一致",
        )
    )

    k, d = stochastic(df)
    results.append(_sign_from_last(k[-1] < 20 and k[-1] > d[-1], k[-1] > 80 and k[-1] < d[-1], 0.6, "stochastic", f"%K={k[-1]:.1f} %D={d[-1]:.1f}"))

    ich = ichimoku(df)
    cloud_top = max(ich["span_a"][-1], ich["span_b"][-1])
    cloud_bot = min(ich["span_a"][-1], ich["span_b"][-1])
    results.append(
        _sign_from_last(
            close[-1] > cloud_top and ich["tenkan"][-1] > ich["kijun"][-1],
            close[-1] < cloud_bot and ich["tenkan"][-1] < ich["kijun"][-1],
            0.75,
            "ichimoku",
            "价格在云层之上" if close[-1] > cloud_top else ("价格在云层之下" if close[-1] < cloud_bot else "价格在云层内"),
        )
    )

    st, st_dir = supertrend(df)
    results.append(IndicatorResult("supertrend", int(st_dir[-1]), 0.8, f"Supertrend={'多' if st_dir[-1] > 0 else '空'} {st[-1]:.6g}"))

    adx, pdi, mdi = adx_dmi(df)
    trend = adx[-1] >= 20
    results.append(
        _sign_from_last(
            trend and pdi[-1] > mdi[-1],
            trend and mdi[-1] > pdi[-1],
            min(1.0, adx[-1] / 50),
            "adx_dmi",
            f"ADX={adx[-1]:.1f} +DI={pdi[-1]:.1f} -DI={mdi[-1]:.1f}",
        )
    )

    wr = williams_r(df)
    results.append(_sign_from_last(wr[-1] < -80, wr[-1] > -20, 0.55, "williams_r", f"W%R={wr[-1]:.1f}"))

    cci_v = cci(df)
    results.append(_sign_from_last(cci_v[-1] < -100, cci_v[-1] > 100, min(1.0, abs(cci_v[-1]) / 200), "cci", f"CCI={cci_v[-1]:.1f}"))

    obv_v = obv(df)
    obv_ema = ema(obv_v, 20)
    results.append(_sign_from_last(obv_v[-1] > obv_ema[-1], obv_v[-1] < obv_ema[-1], 0.45, "obv", "OBV 与均线比较"))

    mfi_v = mfi(df)
    results.append(_sign_from_last(mfi_v[-1] < 20, mfi_v[-1] > 80, 0.55, "mfi", f"MFI={mfi_v[-1]:.1f}"))

    sar = parabolic_sar(df)
    results.append(_sign_from_last(close[-1] > sar[-1], close[-1] < sar[-1], 0.6, "parabolic_sar", f"SAR={sar[-1]:.6g}"))

    atr_v = atr(df, 20)
    k_mid = ema(close, 20)
    k_up, k_lo = k_mid + 1.5 * atr_v, k_mid - 1.5 * atr_v
    results.append(_sign_from_last(close[-1] < k_lo[-1], close[-1] > k_up[-1], 0.5, "keltner", "Keltner 通道"))

    don_h = pd.Series(high).rolling(20, min_periods=1).max().to_numpy()
    don_l = pd.Series(low).rolling(20, min_periods=1).min().to_numpy()
    results.append(_sign_from_last(close[-1] >= don_h[-2], close[-1] <= don_l[-2], 0.7, "donchian", "Donchian 突破"))

    # Fibonacci: last swing
    look = min(80, len(close))
    swing_high = float(np.max(high[-look:]))
    swing_low = float(np.min(low[-look:]))
    rng = max(swing_high - swing_low, 1e-12)
    retr = (close[-1] - swing_low) / rng
    fib_long = retr <= 0.382
    fib_short = retr >= 0.786
    results.append(_sign_from_last(fib_long, fib_short, 0.5, "fibonacci", f"回撤位={retr:.3f}"))

    # Pivot points (classic, last completed bar as previous day proxy)
    pp = (high[-2] + low[-2] + close[-2]) / 3
    r1 = 2 * pp - low[-2]
    s1 = 2 * pp - high[-2]
    results.append(_sign_from_last(close[-1] > pp and close[-1] < r1, close[-1] < pp and close[-1] > s1, 0.4, "pivot_points", f"PP={pp:.6g}"))

    roc_v = roc(close, 12)
    results.append(_sign_from_last(roc_v[-1] > 0 and roc_v[-1] > roc_v[-2], roc_v[-1] < 0 and roc_v[-1] < roc_v[-2], 0.4, "roc", f"ROC={roc_v[-1]:.2f}"))

    cmf_v = cmf(df)
    results.append(_sign_from_last(cmf_v[-1] > 0.05, cmf_v[-1] < -0.05, min(1.0, abs(cmf_v[-1]) * 4), "cmf", f"CMF={cmf_v[-1]:.3f}"))

    trix_v = trix(close)
    results.append(_sign_from_last(trix_v[-1] > 0, trix_v[-1] < 0, 0.4, "trix", f"TRIX={trix_v[-1]:.4f}"))

    vwap_v = vwap(df)
    results.append(_sign_from_last(close[-1] > vwap_v[-1], close[-1] < vwap_v[-1], 0.45, "vwap", f"VWAP={vwap_v[-1]:.6g}"))

    ao = awesome_oscillator(df)
    results.append(_sign_from_last(ao[-1] > 0 and ao[-1] > ao[-2], ao[-1] < 0 and ao[-1] < ao[-2], 0.45, "awesome_oscillator", f"AO={ao[-1]:.6g}"))

    uo = ultimate_oscillator(df)
    results.append(_sign_from_last(uo[-1] < 30, uo[-1] > 70, 0.5, "ultimate_oscillator", f"UO={uo[-1]:.1f}"))

    ha = heikin_ashi(df)
    results.append(_sign_from_last(ha["close"].iloc[-1] > ha["open"].iloc[-1], ha["close"].iloc[-1] < ha["open"].iloc[-1], 0.5, "heikin_ashi", "Heikin-Ashi 蜡烛方向"))

    o, c = df["open"].iloc[-1], df["close"].iloc[-1]
    po, pc = df["open"].iloc[-2], df["close"].iloc[-2]
    bull_eng = pc < po and c > o and c >= po and o <= pc
    bear_eng = pc > po and c < o and c <= po and o >= pc
    results.append(_sign_from_last(bull_eng, bear_eng, 0.8 if bull_eng or bear_eng else 0.1, "engulfing", "吞没形态" if bull_eng or bear_eng else "无吞没"))

    vol = _series(df, "volume")
    vol_sma = sma(vol, 20)
    spike = vol[-1] > vol_sma[-1] * 2
    results.append(_sign_from_last(spike and c > o, spike and c < o, 0.6 if spike else 0.1, "volume_spike", f"量比={vol[-1]/max(vol_sma[-1],1e-12):.2f}"))

    results.append(
        _sign_from_last(
            close[-1] > close[-2] + atr_v[-1],
            close[-1] < close[-2] - atr_v[-1],
            0.55,
            "atr_breakout",
            f"ATR={atr_v[-1]:.6g}",
        )
    )
    return results


def historical_expectancy(df: pd.DataFrame, horizon: int = 8) -> dict[str, float]:
    """Walk a coarse window and score each indicator by forward return alignment."""
    n = len(df)
    if n < 80:
        return {}
    names: dict[str, list[float]] = {}
    span = max(1, n - horizon - 60)
    step = max(8, span // 8)
    for i in range(60, n - horizon, step):
        window = df.iloc[: i + 1]
        try:
            inds = compute_all_indicators(window)
        except Exception:
            continue
        fwd = float(df["close"].iloc[i + horizon] / df["close"].iloc[i] - 1)
        for ind in inds:
            names.setdefault(ind.name, []).append(ind.signal * fwd)
    return {k: float(np.mean(v)) if v else 0.0 for k, v in names.items()}


def last_atr(df: pd.DataFrame, period: int = 14) -> float:
    v = atr(df, period)
    return float(v[-1]) if len(v) else 0.0


def efficiency_ratio(close: np.ndarray, period: int = 20) -> float:
    if len(close) < period + 1:
        return 0.0
    window = close[-(period + 1) :]
    change = abs(float(window[-1] - window[0]))
    vol = float(np.sum(np.abs(np.diff(window))))
    return change / max(vol, 1e-12)


def classify_regime(df: pd.DataFrame) -> dict[str, Any]:
    """Label the latest bar as 震荡 (range), 单边 (trend), or 过渡.

    Mixes ADX, Kaufman efficiency ratio, and Bollinger bandwidth so the
    contract board does not treat chop as a breakout.
    """
    close = _series(df, "close")
    adx, pdi, mdi = adx_dmi(df)
    adx_now = float(adx[-1]) if len(adx) else 0.0
    er = efficiency_ratio(close, 20)
    upper, mid, lower = bollinger(close)
    bw = (upper - lower) / np.maximum(mid, 1e-12)
    look = min(60, len(bw))
    bw_now = float(bw[-1])
    bw_med = float(np.median(bw[-look:])) if look else bw_now
    compressed = bw_now < bw_med * 0.85
    di_spread = abs(float(pdi[-1] - mdi[-1])) if len(pdi) else 0.0

    # ADX stays high on regular swings; ER and DI spread catch the fake trend.
    strong_trend = adx_now >= 25 and er >= 0.32 and di_spread >= 8
    clear_range = (
        er < 0.22
        or (adx_now < 20 and er < 0.30)
        or (di_spread < 6 and er < 0.28)
        or (compressed and er < 0.30)
    )
    if strong_trend and not (er < 0.20):
        regime, code = "单边", "trend"
        advice = "单边行情：可按信号跟方向，用 ATR 止损止盈，不要逆势抄底摸顶。"
        playbook = "单边趋势"
    elif clear_range:
        regime, code = "震荡", "range"
        advice = "震荡行情：不要把来回当突破去追。默认观望；若仍给方向，只做短打、止盈收紧。"
        playbook = "震荡观望"
    else:
        regime, code = "过渡", "mixed"
        advice = "趋势不明：提高开仓门槛，优先观望，等单边或明确震荡再动手。"
        playbook = "过渡谨慎"

    return {
        "regime": regime,
        "regime_code": code,
        "adx": round(adx_now, 1),
        "efficiency": round(er, 3),
        "bb_width": round(bw_now, 4),
        "di_plus": round(float(pdi[-1]), 1) if len(pdi) else 0.0,
        "di_minus": round(float(mdi[-1]), 1) if len(mdi) else 0.0,
        "detail": f"ADX={adx_now:.1f} ER={er:.2f} 带宽={bw_now:.3f}",
        "advice": advice,
        "playbook": playbook,
    }
