from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from web3_radar.config import INITIAL_INDICATOR_SHARES
from web3_radar.engine.indicators import (
    compute_all_indicators,
    last_atr,
)
from web3_radar.engine.monte_carlo import (
    composite_score,
    decision_from_score,
    monte_carlo_reweight,
    normalize_shares,
)
from web3_radar.engine.risk import (
    RiskConfig,
    adaptive_multiples,
    apply_quality_gate,
    plan_note,
    position_plan,
    quality_score,
    trend_agreement,
)


def resolve_weights(
    names: list[str],
    fitted: dict[str, float] | None,
    shares: dict[str, float],
) -> dict[str, float]:
    raw = np.array(
        [
            max(float((fitted or {}).get(n, shares.get(n, 1.0))), 1e-9)
            for n in names
        ],
        dtype=np.float64,
    )
    raw = raw / raw.sum()
    return {n: float(raw[i]) for i, n in enumerate(names)}


def pool_expectancies(maps: list[dict[str, float]], names: list[str]) -> dict[str, float]:
    """Median expectancy per indicator across the universe — more stable than one coin."""
    out: dict[str, float] = {}
    for name in names:
        vals = [float(m[name]) for m in maps if name in m]
        out[name] = float(np.median(vals)) if vals else 0.0
    return out


def fit_global_weights(
    expectancy_maps: list[dict[str, float]],
    names: list[str],
    initial_shares: dict[str, float] | None = None,
    n_sims: int = 1_000_000,
    top_pct: float = 1.0,
    rng: np.random.Generator | None = None,
) -> dict[str, float]:
    shares = initial_shares or INITIAL_INDICATOR_SHARES
    pooled = pool_expectancies(expectancy_maps, names)
    expectancies = np.array([pooled.get(n, 0.0) for n in names], dtype=np.float64)
    if np.allclose(expectancies, 0):
        expectancies = normalize_shares(shares, names) * 0.01
    return monte_carlo_reweight(
        names,
        expectancies,
        initial_shares=shares,
        n_sims=n_sims,
        top_pct=top_pct,
        rng=rng,
    )


def average_weights_from_results(results: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = {}
    for row in results or []:
        for ind in row.get("indicators") or []:
            name = ind.get("name")
            w = ind.get("weight_optimized")
            if not name or w is None:
                continue
            buckets.setdefault(str(name), []).append(float(w))
    if not buckets:
        return {}
    names = list(buckets)
    raw = np.array([float(np.mean(buckets[n])) for n in names], dtype=np.float64)
    raw = raw / max(raw.sum(), 1e-12)
    return {n: float(raw[i]) for i, n in enumerate(names)}


def analyze_klines(
    df: pd.DataFrame,
    symbol: str,
    n_sims: int = 1_000_000,
    threshold: float = 0.22,
    atr_sl_mult: float = 1.8,
    atr_tp_mult: float = 2.8,
    initial_shares: dict[str, float] | None = None,
    top_pct: float = 1.0,
    fitted_weights: dict[str, float] | None = None,
    risk_config: RiskConfig | dict[str, Any] | None = None,
) -> dict[str, Any]:
    if df is None or len(df) < 60:
        raise ValueError("K 线数据不足，至少需要 60 根")
    shares = initial_shares or INITIAL_INDICATOR_SHARES
    if isinstance(risk_config, RiskConfig):
        cfg = risk_config
    elif isinstance(risk_config, dict):
        cfg = RiskConfig.from_settings(
            {
                "signal_threshold": threshold,
                "atr_sl_mult": atr_sl_mult,
                "atr_tp_mult": atr_tp_mult,
                **risk_config,
            }
        )
    else:
        cfg = RiskConfig(threshold=threshold, base_sl_mult=atr_sl_mult, base_tp_mult=atr_tp_mult)

    indicators = compute_all_indicators(df)
    names = [i.name for i in indicators]
    infer = bool(fitted_weights)

    if infer:
        expect_map: dict[str, float] = {}
        weights_map = resolve_weights(names, fitted_weights, shares)
        sim_note = f"套用已拟合权重（校准 {int(n_sims):,} 次），按 ATR 路径风控出仓位"
        mode = "infer"
    else:
        from web3_radar.engine.risk import path_expectancy

        expect_map = path_expectancy(df, cfg)
        expectancies = np.array([expect_map.get(n, 0.0) for n in names], dtype=np.float64)
        if np.allclose(expectancies, 0):
            expectancies = normalize_shares(shares, names) * 0.01
        weights_map = monte_carlo_reweight(
            names,
            expectancies,
            initial_shares=shares,
            n_sims=n_sims,
            top_pct=top_pct,
        )
        sim_note = f"已按 ATR 止盈止损路径完成 {int(n_sims):,} 次蒙特卡洛，并对指标权重做加权平均修正"
        mode = "fit"

    weights = np.array([weights_map[n] for n in names], dtype=np.float64)
    signals = np.array([i.signal for i in indicators], dtype=np.float64)
    strengths = np.array([i.strength for i in indicators], dtype=np.float64)
    score = composite_score(signals, strengths, weights)
    raw_decision = decision_from_score(score, cfg.threshold)
    price = float(df["close"].iloc[-1])
    atr_v = last_atr(df)
    if not math.isfinite(atr_v) or atr_v <= 0:
        atr_v = price * 0.02
    atr_pct = atr_v / price if price else 0.0
    sl_m, tp_m = adaptive_multiples(atr_pct, cfg)

    if raw_decision == "涨":
        raw_side = "long"
        side_sign = 1
    elif raw_decision == "跌":
        raw_side = "short"
        side_sign = -1
    else:
        raw_side = "flat"
        side_sign = 0

    agreement = trend_agreement(indicators, side_sign)
    quality = quality_score(abs(score), agreement, cfg.threshold)
    decision, filter_note = apply_quality_gate(raw_decision, score, agreement, cfg)
    if decision == "涨":
        side = "long"
    elif decision == "跌":
        side = "short"
    else:
        side = "flat"

    plan = position_plan(side if side != "flat" else "long", price, atr_v, sl_m, tp_m, cfg)
    if side == "flat":
        plan["notional_pct"] = 0.0

    return {
        "symbol": symbol,
        "decision": decision,
        "raw_decision": raw_decision,
        "side": side,
        "raw_side": raw_side,
        "score": round(score, 4),
        "confidence": round(min(1.0, abs(score) / max(cfg.threshold, 1e-6)), 4),
        "quality": quality,
        "agreement": round(agreement, 4),
        "tradable": side in {"long", "short"},
        "filter_note": filter_note,
        "price": price,
        "entry": round(price, 8),
        "stop_loss": round(plan["stop_loss"], 8),
        "take_profit": round(plan["take_profit"], 8),
        "partial_tp": round(plan["partial_tp"], 8),
        "breakeven": round(plan["breakeven"], 8),
        "trail_arm": round(plan["trail_arm"], 8),
        "atr": round(atr_v, 8),
        "atr_pct": round(atr_pct, 6),
        "sl_mult": round(sl_m, 4),
        "tp_mult": round(tp_m, 4),
        "stop_pct": plan["stop_pct"],
        "suggested_risk_pct": plan["risk_pct"] if side != "flat" else 0.0,
        "suggested_notional_pct": plan["notional_pct"],
        "plan_note": plan_note(side, plan, atr_pct, sl_m),
        "n_sims": int(n_sims),
        "mode": mode,
        "weights_adjusted": True,
        "sim_note": sim_note,
        "indicators": [
            {
                "name": i.name,
                "signal": i.signal,
                "strength": round(i.strength, 4),
                "detail": i.detail,
                "expectancy": round(float(expect_map.get(i.name, 0.0)), 6),
                "weight_initial": round(float(shares.get(i.name, 1.0)), 4),
                "weight_optimized": round(weights_map[i.name], 4),
            }
            for i in indicators
        ],
    }
