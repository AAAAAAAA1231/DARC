from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import indicators as ta
from .data_source import Bars


@dataclass
class MethodDef:
    name: str
    family: str
    title: str


METHODS: list[MethodDef] = [
    MethodDef("ma_cross_5_20", "trend", "均线金叉(MA5/MA20)"),
    MethodDef("ma_cross_10_60", "trend", "均线金叉(MA10/MA60)"),
    MethodDef("ma_align", "trend", "均线多头排列"),
    MethodDef("macd_hist", "trend", "MACD柱"),
    MethodDef("macd_dif", "trend", "MACD DIF"),
    MethodDef("trix", "trend", "TRIX"),
    MethodDef("dmi_adx", "trend", "DMI/ADX"),
    MethodDef("ichimoku", "trend", "一目均衡"),
    MethodDef("supertrend", "trend", "Supertrend"),
    MethodDef("rsi_mr", "oscillator", "RSI均值回归"),
    MethodDef("rsi_mom", "oscillator", "RSI动量"),
    MethodDef("kdj_j", "oscillator", "KDJ"),
    MethodDef("cci", "oscillator", "CCI"),
    MethodDef("williams", "oscillator", "威廉指标"),
    MethodDef("bias", "oscillator", "乖离率"),
    MethodDef("psy", "oscillator", "心理线"),
    MethodDef("roc", "momentum", "ROC变动率"),
    MethodDef("mom20", "momentum", "20日动量"),
    MethodDef("boll_break", "breakout", "布林突破"),
    MethodDef("boll_revert", "meanrev", "布林回归"),
    MethodDef("donchian", "breakout", "唐奇安/海龟"),
    MethodDef("atr_break", "breakout", "ATR通道突破"),
    MethodDef("keltner", "breakout", "肯特纳通道"),
    MethodDef("dual_thrust", "breakout", "Dual Thrust"),
    MethodDef("support_resist", "structure", "支撑阻力"),
    MethodDef("gap", "structure", "缺口"),
    MethodDef("obv", "volume", "OBV能量潮"),
    MethodDef("mfi", "volume", "资金流量MFI"),
    MethodDef("vr", "volume", "成交量比率VR"),
    MethodDef("vol_price", "volume", "量价齐升"),
    MethodDef("vwap_dev", "meanrev", "VWAP偏离"),
    MethodDef("hv_revert", "volatility", "波动率回归"),
]


def method_names() -> list[str]:
    return [m.name for m in METHODS]


def _tanh(x: np.ndarray | float, scale: float = 1.0) -> np.ndarray:
    return np.tanh(np.asarray(x, dtype=float) / scale)


def _safe_div(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a / np.where(b == 0, np.nan, b)


def compute_features(bars: Bars) -> dict[str, np.ndarray]:
    o, h, l, c, v = bars.open, bars.high, bars.low, bars.close, bars.volume
    ma5, ma10, ma20, ma60 = ta.sma(c, 5), ta.sma(c, 10), ta.sma(c, 20), ta.sma(c, 60)
    dif, dea, hist = ta.macd(c)
    k, d, j = ta.kdj(h, l, c)
    mid, upper, lower, width = ta.bollinger(c)
    plus_di, minus_di, adx = ta.dmi_adx(h, l, c)
    atr14 = ta.atr(h, l, c, 14)
    don_h, don_l = ta.donchian(h, l, 20)
    k_mid, k_up, k_lo = ta.keltner(h, l, c)
    hh20, ll20 = ta.rolling_max(h, 20), ta.rolling_min(l, 20)
    rng20 = hh20 - ll20
    tenkan = (ta.rolling_max(h, 9) + ta.rolling_min(l, 9)) / 2.0
    kijun = (ta.rolling_max(h, 26) + ta.rolling_min(l, 26)) / 2.0
    senkou_b = (ta.rolling_max(h, 52) + ta.rolling_min(l, 52)) / 2.0
    span_a = (tenkan + kijun) / 2.0
    prev_close = np.concatenate([[c[0]], c[:-1]])
    gap = _safe_div(o - prev_close, prev_close)
    ret1 = _safe_div(c - prev_close, prev_close)
    vol_ma = ta.sma(v, 20)
    obv = ta.obv(c, v)
    st_dir = np.sign(c - ta.ema(c, 21))
    st_dir = np.where(st_dir == 0, 1.0, st_dir)
    return {
        "close": c,
        "open": o,
        "high": h,
        "low": l,
        "volume": v,
        "ma5": ma5,
        "ma10": ma10,
        "ma20": ma20,
        "ma60": ma60,
        "dif": dif,
        "dea": dea,
        "hist": hist,
        "k": k,
        "d": d,
        "j": j,
        "rsi": ta.rsi(c),
        "cci": ta.cci(h, l, c),
        "wr": ta.williams_r(h, l, c),
        "bias6": ta.bias(c, 6),
        "bias24": ta.bias(c, 24),
        "psy": ta.psy(c),
        "roc12": ta.roc(c, 12),
        "roc20": ta.roc(c, 20),
        "boll_mid": mid,
        "boll_up": upper,
        "boll_lo": lower,
        "boll_w": width,
        "plus_di": plus_di,
        "minus_di": minus_di,
        "adx": adx,
        "trix": ta.trix(c),
        "atr": atr14,
        "don_h": don_h,
        "don_l": don_l,
        "kelt_mid": k_mid,
        "kelt_up": k_up,
        "kelt_lo": k_lo,
        "obv": obv,
        "obv_ma": ta.sma(obv, 20),
        "mfi": ta.mfi(h, l, c, v),
        "vr": ta.vr(c, v),
        "vwap": ta.vwap(h, l, c, v),
        "hv20": ta.rolling_hv(c, 20),
        "hv60": ta.rolling_hv(c, 60),
        "tenkan": tenkan,
        "kijun": kijun,
        "span_a": span_a,
        "span_b": senkou_b,
        "st_dir": st_dir,
        "gap": gap,
        "ret1": ret1,
        "vol_ma": vol_ma,
        "hh20": hh20,
        "ll20": ll20,
        "rng20": rng20,
    }


def score_series(name: str, feat: dict[str, np.ndarray]) -> np.ndarray:
    c = feat["close"]
    atr = np.where(feat["atr"] == 0, np.nan, feat["atr"])
    if name == "ma_cross_5_20":
        return _tanh(_safe_div(feat["ma5"] - feat["ma20"], atr), 1.2)
    if name == "ma_cross_10_60":
        return _tanh(_safe_div(feat["ma10"] - feat["ma60"], atr), 1.5)
    if name == "ma_align":
        bull = (feat["ma5"] > feat["ma10"]).astype(float) + (feat["ma10"] > feat["ma20"]).astype(float) + (
            feat["ma20"] > feat["ma60"]
        ).astype(float)
        return (bull - 1.5) / 1.5
    if name == "macd_hist":
        return _tanh(_safe_div(feat["hist"], atr), 1.0)
    if name == "macd_dif":
        sign = np.sign(feat["dif"] - feat["dea"])
        return _tanh(_safe_div(feat["dif"], atr), 1.5) * 0.7 + 0.3 * sign
    if name == "trix":
        return _tanh(feat["trix"], 0.4)
    if name == "dmi_adx":
        raw = _safe_div(feat["plus_di"] - feat["minus_di"], 40.0)
        strength = np.clip(feat["adx"] / 40.0, 0, 1.5)
        return np.clip(raw * strength, -1, 1)
    if name == "ichimoku":
        cloud_top = np.maximum(feat["span_a"], feat["span_b"])
        cloud_bot = np.minimum(feat["span_a"], feat["span_b"])
        above = (c > cloud_top).astype(float)
        below = (c < cloud_bot).astype(float)
        tk = np.sign(feat["tenkan"] - feat["kijun"])
        return np.clip(0.6 * (above - below) + 0.4 * tk, -1, 1)
    if name == "supertrend":
        return feat["st_dir"]
    if name == "rsi_mr":
        return np.clip((50.0 - feat["rsi"]) / 30.0, -1, 1)
    if name == "rsi_mom":
        return np.clip((feat["rsi"] - 50.0) / 30.0, -1, 1)
    if name == "kdj_j":
        return np.clip((50.0 - feat["j"]) / 40.0, -1, 1)
    if name == "cci":
        return np.clip(feat["cci"] / 150.0, -1, 1)
    if name == "williams":
        return np.clip((-feat["wr"] - 50.0) / 30.0, -1, 1)
    if name == "bias":
        return np.clip(-feat["bias6"] / 8.0, -1, 1)
    if name == "psy":
        return np.clip((feat["psy"] - 50.0) / 25.0, -1, 1)
    if name == "roc":
        return _tanh(feat["roc12"], 6.0)
    if name == "mom20":
        return _tanh(feat["roc20"], 8.0)
    if name == "boll_break":
        pos = _safe_div(c - feat["boll_mid"], feat["boll_up"] - feat["boll_lo"])
        squeeze = np.clip(0.08 / np.where(feat["boll_w"] == 0, np.nan, feat["boll_w"]), 0, 2)
        return np.clip(pos * 4.0 * squeeze, -1, 1)
    if name == "boll_revert":
        pos = _safe_div(c - feat["boll_mid"], (feat["boll_up"] - feat["boll_lo"]) / 2.0)
        return np.clip(-pos, -1, 1)
    if name == "donchian":
        width = feat["don_h"] - feat["don_l"]
        loc = _safe_div(c - feat["don_l"], width)
        return np.clip((loc - 0.5) * 2.0, -1, 1)
    if name == "atr_break":
        return np.clip(_safe_div(c - feat["ma20"], 2.0 * atr), -1, 1)
    if name == "keltner":
        loc = _safe_div(c - feat["kelt_mid"], feat["kelt_up"] - feat["kelt_lo"])
        return np.clip(loc * 3.0, -1, 1)
    if name == "dual_thrust":
        rng = feat["rng20"]
        buy = feat["open"] + 0.5 * rng
        sell = feat["open"] - 0.5 * rng
        score = np.where(c > buy, _safe_div(c - buy, atr), np.where(c < sell, _safe_div(c - sell, atr), 0.0))
        return np.clip(score, -1, 1)
    if name == "support_resist":
        loc = _safe_div(c - feat["ll20"], feat["hh20"] - feat["ll20"])
        # near high -> breakout long; near low -> bounce long for A-share mean-reversion blend
        breakout = np.clip((loc - 0.85) / 0.15, 0, 1) - np.clip((0.15 - loc) / 0.15, 0, 1)
        bounce = np.clip((0.2 - loc) / 0.2, 0, 1) - np.clip((loc - 0.8) / 0.2, 0, 1)
        return np.clip(0.55 * breakout + 0.45 * bounce, -1, 1)
    if name == "gap":
        return np.clip(feat["gap"] / 0.03, -1, 1)
    if name == "obv":
        return _tanh(_safe_div(feat["obv"] - feat["obv_ma"], np.abs(feat["obv_ma"]) + 1.0), 0.4)
    if name == "mfi":
        return np.clip((feat["mfi"] - 50.0) / 30.0, -1, 1)
    if name == "vr":
        return np.clip((feat["vr"] - 100.0) / 80.0, -1, 1)
    if name == "vol_price":
        vol_r = _safe_div(feat["volume"], feat["vol_ma"])
        px = np.sign(feat["ret1"])
        return np.clip(px * np.clip(vol_r - 0.8, -1, 2) / 2.0, -1, 1)
    if name == "vwap_dev":
        return np.clip(-_safe_div(c - feat["vwap"], atr), -1, 1)
    if name == "hv_revert":
        ratio = _safe_div(feat["hv20"], feat["hv60"])
        # high vol -> fade; low vol -> breakout bias via 0
        return np.clip(1.1 - ratio, -1, 1) * np.sign(feat["ret1"] + 1e-12) * -0.5 + np.clip(
            (1.0 - ratio) * 0.5, -1, 1
        )
    raise KeyError(name)


def all_score_matrix(bars: Bars) -> tuple[list[str], np.ndarray]:
    feat = compute_features(bars)
    names = method_names()
    matrix = np.column_stack([score_series(name, feat) for name in names])
    return names, np.nan_to_num(matrix, nan=0.0, posinf=0.0, neginf=0.0)


def last_signals(bars: Bars) -> list[dict]:
    feat = compute_features(bars)
    rows = []
    for method in METHODS:
        series = score_series(method.name, feat)
        score = float(series[-1]) if np.isfinite(series[-1]) else 0.0
        score = float(np.clip(score, -1, 1))
        rows.append(
            {
                "name": method.name,
                "title": method.title,
                "family": method.family,
                "score": round(score, 4),
                "confidence": round(min(1.0, abs(score) * 1.15), 4),
            }
        )
    return rows
