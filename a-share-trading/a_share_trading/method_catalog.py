from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
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
