from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Sequence

import numpy as np
import pandas as pd

from web3_radar.engine.indicators import IndicatorResult, atr, compute_all_indicators

TREND_INDICATORS = (
    "supertrend",
    "ema_cross",
    "ichimoku",
    "adx_dmi",
    "parabolic_sar",
    "macd",
    "donchian",
)


@dataclass(frozen=True)
class RiskConfig:
    threshold: float = 0.22
    base_sl_mult: float = 1.8
    base_tp_mult: float = 2.8
    high_vol_pct: float = 0.035
    low_vol_pct: float = 0.018
    high_vol_scale: float = 1.22
    low_vol_scale: float = 0.89
    partial_tp_r: float = 1.0
    partial_tp_frac: float = 0.40
    breakeven_r: float = 1.0
    trail_arm_r: float = 1.5
    trail_atr_mult: float = 1.0
    risk_per_trade_pct: float = 0.5
    max_notional_pct: float = 25.0
    max_positions: int = 3
    max_same_side: int = 2
    min_trend_agreement: float = 0.45
    path_horizon: int = 16

    @classmethod
    def from_settings(cls, settings: dict[str, Any] | None) -> "RiskConfig":
        s = settings or {}
        return cls(
            threshold=float(s.get("signal_threshold") or cls.threshold),
            base_sl_mult=float(s.get("atr_sl_mult") or cls.base_sl_mult),
            base_tp_mult=float(s.get("atr_tp_mult") or cls.base_tp_mult),
            risk_per_trade_pct=float(s.get("risk_per_trade_pct") or cls.risk_per_trade_pct),
            max_positions=int(s.get("max_contract_positions") or cls.max_positions),
            max_same_side=int(s.get("max_same_side_positions") or cls.max_same_side),
            min_trend_agreement=float(s.get("min_trend_agreement") or cls.min_trend_agreement),
            partial_tp_r=float(s.get("partial_tp_r") or cls.partial_tp_r),
            partial_tp_frac=float(s.get("partial_tp_frac") or cls.partial_tp_frac),
            breakeven_r=float(s.get("breakeven_r") or cls.breakeven_r),
            trail_arm_r=float(s.get("trail_arm_r") or cls.trail_arm_r),
            trail_atr_mult=float(s.get("trail_atr_mult") or cls.trail_atr_mult),
        )


def adaptive_multiples(atr_pct: float, cfg: RiskConfig | None = None) -> tuple[float, float]:
    """Widen stops for high-vol alts (HYPE/ZEC class) and tighten slightly for majors."""
    cfg = cfg or RiskConfig()
    pct = max(float(atr_pct), 0.0)
    if pct >= cfg.high_vol_pct:
        scale = cfg.high_vol_scale
    elif pct <= cfg.low_vol_pct:
        scale = cfg.low_vol_scale
    else:
        scale = 1.0
    return cfg.base_sl_mult * scale, cfg.base_tp_mult * scale


def trend_agreement(indicators: Sequence[IndicatorResult] | Sequence[dict[str, Any]], side_sign: int) -> float:
    """0-1 score of whether trend indicators agree with the proposed side."""
    if side_sign == 0:
        return 0.0
    num = 0.0
    den = 0.0
    for item in indicators:
        if isinstance(item, dict):
            name = str(item.get("name") or "")
            signal = int(item.get("signal") or 0)
            strength = float(item.get("strength") or 0.0)
        else:
            name = item.name
            signal = int(item.signal)
            strength = float(item.strength)
        if name not in TREND_INDICATORS:
            continue
        w = max(strength, 0.15)
        den += w
        if signal == side_sign:
            num += w
        elif signal == -side_sign:
            num -= 0.5 * w
    if den <= 0:
        return 0.0
    return float(np.clip((num / den + 1.0) / 2.0, 0.0, 1.0))


def quality_score(abs_score: float, agreement: float, threshold: float) -> float:
    if threshold <= 0:
        threshold = 0.22
    scaled = abs(float(abs_score)) / threshold
    return round(float(scaled * (0.35 + 0.65 * float(agreement))), 4)


def position_plan(
    side: str,
    entry: float,
    atr_v: float,
    sl_mult: float,
    tp_mult: float,
    cfg: RiskConfig | None = None,
) -> dict[str, Any]:
    cfg = cfg or RiskConfig()
    if entry <= 0 or atr_v <= 0:
        raise ValueError("entry and ATR must be positive")
    if side == "short":
        sl = entry + sl_mult * atr_v
        tp = entry - tp_mult * atr_v
        partial = entry - cfg.partial_tp_r * sl_mult * atr_v
    else:
        sl = entry - sl_mult * atr_v
        tp = entry + tp_mult * atr_v
        partial = entry + cfg.partial_tp_r * sl_mult * atr_v
    stop_pct = abs(entry - sl) / entry * 100.0
    risk_pct = max(cfg.risk_per_trade_pct, 0.0)
    notional_pct = 0.0
    if stop_pct > 0 and side in {"long", "short"}:
        notional_pct = min(cfg.max_notional_pct, risk_pct / stop_pct * 100.0)
    return {
        "stop_loss": sl,
        "take_profit": tp,
        "partial_tp": partial,
        "breakeven": entry,
        "trail_arm": _trail_arm_price(side, entry, atr_v, sl_mult, cfg),
        "trail_offset": cfg.trail_atr_mult * atr_v,
        "stop_pct": round(stop_pct, 4),
        "risk_pct": risk_pct,
        "notional_pct": round(notional_pct, 3),
        "rr": round(tp_mult / max(sl_mult, 1e-9), 3),
        "partial_frac": cfg.partial_tp_frac,
        "partial_r": cfg.partial_tp_r,
        "breakeven_r": cfg.breakeven_r,
        "trail_arm_r": cfg.trail_arm_r,
    }


def _trail_arm_price(side: str, entry: float, atr_v: float, sl_mult: float, cfg: RiskConfig) -> float:
    move = cfg.trail_arm_r * sl_mult * atr_v
    return entry - move if side == "short" else entry + move


def size_equal_notional(pnls: Iterable[float]) -> float:
    return float(sum(pnls))


def size_risk_parity(returns_pct: Sequence[float], stop_pcts: Sequence[float], risk_unit: float = 1.0) -> float:
    """Each name risks `risk_unit` at its own stop. `returns_pct` and `stop_pcts` are percent numbers."""
    total = 0.0
    for ret, stop in zip(returns_pct, stop_pcts, strict=False):
        if stop <= 0:
            continue
        r_mult = ret / stop
        total += r_mult * risk_unit
    return float(total)


def simulate_trade_r(
    highs: np.ndarray,
    lows: np.ndarray,
    side: int,
    entry: float,
    sl: float,
    tp: float,
    atr_v: float,
    cfg: RiskConfig | None = None,
    manage: bool = True,
) -> float:
    """Path P&L in R (initial risk units) using subsequent bar highs/lows."""
    cfg = cfg or RiskConfig()
    if side == 0 or entry <= 0:
        return 0.0
    risk = abs(entry - sl)
    if risk <= 1e-12:
        return 0.0
    remaining = 1.0
    realized = 0.0
    stop = sl
    taken_partial = False
    moved_be = False
    high = np.asarray(highs, dtype=np.float64)
    low = np.asarray(lows, dtype=np.float64)
    n = min(len(high), len(low))
    trail_off = cfg.trail_atr_mult * atr_v
    for i in range(n):
        h = float(high[i])
        l = float(low[i])
        if side > 0:
            hit_sl = l <= stop
            hit_tp = h >= tp
            mfe = (h - entry) / risk
            if hit_sl and hit_tp:
                realized += remaining * ((stop - entry) / risk)
                remaining = 0.0
                break
            if hit_sl:
                realized += remaining * ((stop - entry) / risk)
                remaining = 0.0
                break
            if manage and (not taken_partial) and mfe >= cfg.partial_tp_r:
                realized += cfg.partial_tp_frac * cfg.partial_tp_r
                remaining -= cfg.partial_tp_frac
                taken_partial = True
            if manage and (not moved_be) and mfe >= cfg.breakeven_r:
                stop = max(stop, entry)
                moved_be = True
            if manage and mfe >= cfg.trail_arm_r:
                stop = max(stop, h - trail_off)
            if hit_tp:
                realized += remaining * ((tp - entry) / risk)
                remaining = 0.0
                break
        else:
            hit_sl = h >= stop
            hit_tp = l <= tp
            mfe = (entry - l) / risk
            if hit_sl and hit_tp:
                realized += remaining * ((entry - stop) / risk)
                remaining = 0.0
                break
            if hit_sl:
                realized += remaining * ((entry - stop) / risk)
                remaining = 0.0
                break
            if manage and (not taken_partial) and mfe >= cfg.partial_tp_r:
                realized += cfg.partial_tp_frac * cfg.partial_tp_r
                remaining -= cfg.partial_tp_frac
                taken_partial = True
            if manage and (not moved_be) and mfe >= cfg.breakeven_r:
                stop = min(stop, entry)
                moved_be = True
            if manage and mfe >= cfg.trail_arm_r:
                stop = min(stop, l + trail_off)
            if hit_tp:
                realized += remaining * ((entry - tp) / risk)
                remaining = 0.0
                break
    if remaining > 0 and n:
        last_mid = (float(high[-1]) + float(low[-1])) / 2.0
        realized += remaining * (side * (last_mid - entry) / risk)
    return float(realized)


def path_expectancy(df: pd.DataFrame, cfg: RiskConfig | None = None) -> dict[str, float]:
    """Score indicators by ATR-stop path R, not close-to-close forward return."""
    cfg = cfg or RiskConfig()
    n = len(df)
    horizon = int(cfg.path_horizon)
    if n < 80:
        return {}
    highs = df["high"].to_numpy(dtype=np.float64)
    lows = df["low"].to_numpy(dtype=np.float64)
    closes = df["close"].to_numpy(dtype=np.float64)
    atr_s = atr(df, 14)
    names: dict[str, list[float]] = {}
    span = max(1, n - horizon - 60)
    step = max(8, span // 8)
    for i in range(60, n - horizon, step):
        window = df.iloc[: i + 1]
        try:
            inds = compute_all_indicators(window)
        except Exception:
            continue
        price = float(closes[i])
        atr_v = float(atr_s[i]) if np.isfinite(atr_s[i]) and atr_s[i] > 0 else price * 0.02
        atr_pct = atr_v / price
        sl_m, tp_m = adaptive_multiples(atr_pct, cfg)
        for ind in inds:
            if ind.signal == 0:
                continue
            if ind.signal > 0:
                sl = price - sl_m * atr_v
                tp = price + tp_m * atr_v
            else:
                sl = price + sl_m * atr_v
                tp = price - tp_m * atr_v
            r = simulate_trade_r(
                highs[i + 1 : i + 1 + horizon],
                lows[i + 1 : i + 1 + horizon],
                int(ind.signal),
                price,
                sl,
                tp,
                atr_v,
                cfg,
                manage=True,
            )
            names.setdefault(ind.name, []).append(r)
    return {k: float(np.mean(v)) if v else 0.0 for k, v in names.items()}


def apply_quality_gate(
    raw_decision: str,
    score: float,
    agreement: float,
    cfg: RiskConfig | None = None,
) -> tuple[str, str]:
    cfg = cfg or RiskConfig()
    if raw_decision == "观望":
        return "观望", ""
    q = quality_score(abs(score), agreement, cfg.threshold)
    strong = abs(score) >= 2.0 * cfg.threshold
    if agreement < cfg.min_trend_agreement and not strong:
        return "观望", f"趋势指标分歧（一致度 {agreement:.2f} < {cfg.min_trend_agreement:.2f}），不做"
    if q < 0.70:
        return "观望", f"信号质量 {q:.2f} 偏低，不做"
    return raw_decision, ""


def apply_portfolio_overlay(results: list[dict[str, Any]], cfg: RiskConfig | None = None) -> list[dict[str, Any]]:
    """Keep at most N highest-quality names and at most K of the same side."""
    cfg = cfg or RiskConfig()
    ranked = sorted(
        [r for r in results if r.get("side") in {"long", "short"} and not r.get("error")],
        key=lambda r: (float(r.get("quality") or 0.0), abs(float(r.get("score") or 0.0))),
        reverse=True,
    )
    taken: list[str] = []
    longs = 0
    shorts = 0
    chosen: set[str] = set()
    for row in ranked:
        sym = str(row.get("symbol") or "")
        side = row.get("side")
        if len(taken) >= cfg.max_positions:
            row["decision"] = "观望"
            row["side"] = "flat"
            row["tradable"] = False
            row["filter_note"] = (row.get("filter_note") or "") or f"组合已满，只保留质量最高的 {cfg.max_positions} 个"
            row["suggested_notional_pct"] = 0.0
            continue
        if side == "long" and longs >= cfg.max_same_side:
            row["decision"] = "观望"
            row["side"] = "flat"
            row["tradable"] = False
            row["filter_note"] = f"同向多头已满 {cfg.max_same_side} 个，避免相关暴露"
            row["suggested_notional_pct"] = 0.0
            continue
        if side == "short" and shorts >= cfg.max_same_side:
            row["decision"] = "观望"
            row["side"] = "flat"
            row["tradable"] = False
            row["filter_note"] = f"同向空头已满 {cfg.max_same_side} 个，避免相关暴露"
            row["suggested_notional_pct"] = 0.0
            continue
        taken.append(sym)
        chosen.add(sym)
        row["tradable"] = True
        row["book_rank"] = len(taken)
        if side == "long":
            longs += 1
        else:
            shorts += 1
    for row in results:
        if row.get("symbol") in chosen:
            continue
        if row.get("side") in {"long", "short"} and not row.get("filter_note"):
            row["decision"] = "观望"
            row["side"] = "flat"
            row["tradable"] = False
            row["suggested_notional_pct"] = 0.0
        elif row.get("side") not in {"long", "short"}:
            row["tradable"] = False
            row["suggested_notional_pct"] = 0.0
    return results


def plan_note(side: str, plan: dict[str, Any], atr_pct: float, sl_mult: float) -> str:
    if side not in {"long", "short"}:
        return "观望，不建仓。"
    vol = "高波动" if atr_pct >= 0.035 else ("低波动" if atr_pct <= 0.018 else "中波动")
    return (
        f"{vol} · 止损 {sl_mult:.2f} ATR（约 {plan['stop_pct']:.2f}%）· "
        f"建议名义仓位 {plan['notional_pct']:.1f}% 权益（单笔风险 {plan['risk_pct']:.2f}%）· "
        f"浮盈 {plan['partial_r']:.1f}R 减仓 {int(plan['partial_frac']*100)}%，"
        f"同时把止损移到成本；{plan['trail_arm_r']:.1f}R 后按 ATR 追踪。"
        "不同标的按止损距离配仓，不要按名义金额均分。"
    )


def config_public(cfg: RiskConfig) -> dict[str, Any]:
    return asdict(cfg)
