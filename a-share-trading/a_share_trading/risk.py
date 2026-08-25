from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .data_source import Bars, Stock
from .ensemble import EnsembleResult
from .indicators import atr, rolling_max, rolling_min


@dataclass
class RiskPlan:
    side: str
    entry: float
    take_profit: float
    stop_loss: float
    reward_risk: float
    atr: float
    limit_pct: float
    notes: str


def _round_px(price: float) -> float:
    if price >= 1000:
        return round(price, 1)
    if price >= 100:
        return round(price, 2)
    return round(price, 3 if price < 10 else 2)


def build_risk_plan(stock: Stock, bars: Bars, ensemble: EnsembleResult) -> RiskPlan:
    price = float(bars.close[-1] if len(bars) else stock.last)
    atr14 = float(atr(bars.high, bars.low, bars.close, 14)[-1])
    if not np.isfinite(atr14) or atr14 <= 0:
        atr14 = max(price * 0.02, 0.01)
    hh = float(rolling_max(bars.high, 20)[-1])
    ll = float(rolling_min(bars.low, 20)[-1])
    limit = max(float(stock.limit_pct), 0.05)
    conf = ensemble.confidence
    score = ensemble.score
    horizon = max(ensemble.horizon_days, 1)
    # Scale ATR for multi-day holding, but cap by board limit path.
    move = atr14 * (0.9 + 0.6 * conf) * (horizon ** 0.5) / (5 ** 0.5)
    if ensemble.direction == "上涨":
        side = "做多"
        stop = price - max(1.6 * atr14, move * 0.85)
        take = price + max(2.4 * atr14, move * 1.35)
        # structural levels
        if ll < price:
            stop = max(stop, ll * 0.995)
        if hh > price:
            take = max(take, min(hh * 1.01, price * (1 + limit * 2.2)))
    elif ensemble.direction == "下跌":
        side = "做空/规避"
        stop = price + max(1.6 * atr14, move * 0.85)
        take = price - max(2.4 * atr14, move * 1.35)
        if hh > price:
            stop = min(stop, hh * 1.005)
        if ll < price:
            take = min(take, max(ll * 0.99, price * (1 - limit * 2.2)))
    else:
        side = "观望"
        band = max(1.2 * atr14, price * 0.015)
        stop = price - band
        take = price + band * (0.8 + 0.4 * abs(score))

    floor = price * (1 - min(limit * 2.4, 0.45))
    ceil = price * (1 + min(limit * 2.4, 0.45))
    stop = float(np.clip(stop, floor, ceil))
    take = float(np.clip(take, floor, ceil))
    if side.startswith("做多") and take <= price:
        take = min(ceil, price + 1.5 * atr14)
    if side.startswith("做空") and take >= price:
        take = max(floor, price - 1.5 * atr14)
    if side.startswith("做多"):
        risk = max(price - stop, 1e-6)
        reward = max(take - price, 0.0)
    elif side.startswith("做空"):
        risk = max(stop - price, 1e-6)
        reward = max(price - take, 0.0)
    else:
        risk = max(price - stop, 1e-6)
        reward = max(take - price, 0.0)
    notes = (
        f"{stock.board} 日涨跌幅限制 {limit:.0%}；"
        f"ATR14={atr14:.3f}；持有期约 {horizon} 日；"
        f"置信度 {conf:.0%}。"
    )
    if stock.limit_pct <= 0.05:
        notes += " ST 股票波动受限，止盈止损已按 5% 板压缩。"
    return RiskPlan(
        side=side,
        entry=_round_px(price),
        take_profit=_round_px(take),
        stop_loss=_round_px(stop),
        reward_risk=round(float(reward / risk), 2),
        atr=round(atr14, 4),
        limit_pct=limit,
        notes=notes,
    )
