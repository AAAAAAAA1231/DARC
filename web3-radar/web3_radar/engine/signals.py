from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd

from web3_radar.config import INITIAL_INDICATOR_SHARES
from web3_radar.engine.indicators import (
    classify_regime,
    compute_all_indicators,
    historical_expectancy,
    last_atr,
)
from web3_radar.engine.monte_carlo import (
    composite_score,
    decision_from_score,
    monte_carlo_reweight,
    normalize_shares,
)

MIN_SUCCESS_RATE = 0.80
MIN_SUCCESS_SAMPLES = 6


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


def directional_hit_rate(
    df: pd.DataFrame,
    weights_map: dict[str, float],
    threshold: float,
    horizon: int = 8,
    max_windows: int = 8,
) -> tuple[float, int]:
    """Walk recent history: when the model would have said 涨/跌, how often the next bars agreed."""
    n = len(df)
    if n < 80:
        return 0.0, 0
    hits = 0
    total = 0
    span = max(1, n - horizon - 60)
    step = max(6, span // max(max_windows, 1))
    for i in range(60, n - horizon, step):
        window = df.iloc[: i + 1]
        try:
            inds = compute_all_indicators(window)
        except Exception:
            continue
        names = [ind.name for ind in inds]
        weights = np.array([float(weights_map.get(name, 1.0)) for name in names], dtype=np.float64)
        if weights.sum() <= 0:
            continue
        weights = weights / weights.sum()
        signals = np.array([ind.signal for ind in inds], dtype=np.float64)
        strengths = np.array([ind.strength for ind in inds], dtype=np.float64)
        score = composite_score(signals, strengths, weights)
        decision = decision_from_score(score, threshold)
        if decision == "观望":
            continue
        fwd = float(df["close"].iloc[i + horizon] / df["close"].iloc[i] - 1)
        if (decision == "涨" and fwd > 0) or (decision == "跌" and fwd < 0):
            hits += 1
        total += 1
        if total >= max_windows:
            break
    if total <= 0:
        return 0.0, 0
    return float(hits / total), int(total)


def apply_success_gate(
    decision: str,
    rate: float,
    samples: int,
    min_rate: float = MIN_SUCCESS_RATE,
    min_samples: int = MIN_SUCCESS_SAMPLES,
) -> tuple[str, bool, str]:
    if decision == "观望":
        return "观望", False, "未形成方向，不推荐"
    if samples < min_samples:
        return "观望", False, f"样本不足（{samples} 次），不推荐"
    if rate + 1e-12 < min_rate:
        return "观望", False, f"成功率 {rate:.0%} < 80%，不推荐"
    return decision, True, f"成功率 {rate:.0%}（{samples} 次回看）"


def analyze_klines(
    df: pd.DataFrame,
    symbol: str,
    n_sims: int = 1_000_000,
    threshold: float = 0.18,
    atr_sl_mult: float = 1.5,
    atr_tp_mult: float = 2.5,
    initial_shares: dict[str, float] | None = None,
    top_pct: float = 1.0,
    fitted_weights: dict[str, float] | None = None,
    min_success_rate: float = MIN_SUCCESS_RATE,
) -> dict[str, Any]:
    if df is None or len(df) < 60:
        raise ValueError("K 线数据不足，至少需要 60 根")
    shares = initial_shares or INITIAL_INDICATOR_SHARES
    indicators = compute_all_indicators(df)
    names = [i.name for i in indicators]
    infer = bool(fitted_weights)

    if infer:
        expect_map: dict[str, float] = {}
        weights_map = resolve_weights(names, fitted_weights, shares)
        sim_note = f"套用已拟合权重（校准 {int(n_sims):,} 次），不再重复蒙特卡洛"
        mode = "infer"
    else:
        expect_map = historical_expectancy(df)
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
        sim_note = f"已按初始份额完成 {int(n_sims):,} 次蒙特卡洛模拟，并对指标权重做加权平均修正"
        mode = "fit"

    weights = np.array([weights_map[n] for n in names], dtype=np.float64)
    signals = np.array([i.signal for i in indicators], dtype=np.float64)
    strengths = np.array([i.strength for i in indicators], dtype=np.float64)
    score = composite_score(signals, strengths, weights)
    raw_decision = decision_from_score(score, threshold)
    regime_info = classify_regime(df)
    regime = str(regime_info.get("regime") or "过渡")
    sl_m, tp_m = float(atr_sl_mult), float(atr_tp_mult)
    effective_threshold = float(threshold)

    if regime == "震荡":
        # Chop killed trend-follow yesterday: raise the bar and tighten targets.
        effective_threshold = threshold * 1.8
        sl_m, tp_m = min(sl_m, 1.0), min(tp_m, 1.2)
        decision = decision_from_score(score, effective_threshold)
        regime_info["playbook"] = "震荡短打" if decision != "观望" else "震荡观望"
        if decision == "观望" and raw_decision != "观望":
            sim_note = f"{sim_note} · 当前震荡，已忽略趋势向的{raw_decision}信号"
    elif regime == "过渡":
        effective_threshold = threshold * 1.35
        tp_m = tp_m * 0.8
        decision = decision_from_score(score, effective_threshold)
        if decision == "观望" and raw_decision != "观望":
            sim_note = f"{sim_note} · 趋势不明，暂不跟{raw_decision}"
    else:
        decision = raw_decision

    hit_rate, hit_n = directional_hit_rate(df, weights_map, effective_threshold)
    decision, recommend, gate_note = apply_success_gate(
        decision, hit_rate, hit_n, min_rate=float(min_success_rate)
    )
    if not recommend:
        side = "flat"
        sim_note = f"{sim_note} · {gate_note}"
    else:
        sim_note = f"{sim_note} · {gate_note}"

    price = float(df["close"].iloc[-1])
    atr_v = last_atr(df)
    if not math.isfinite(atr_v) or atr_v <= 0:
        atr_v = price * 0.02

    if decision == "涨":
        entry, sl, tp = price, price - sl_m * atr_v, price + tp_m * atr_v
        side = "long"
    elif decision == "跌":
        entry, sl, tp = price, price + sl_m * atr_v, price - tp_m * atr_v
        side = "short"
    else:
        entry, sl, tp = price, price - sl_m * atr_v, price + tp_m * atr_v
        side = "flat"

    return {
        "symbol": symbol,
        "decision": decision,
        "raw_decision": raw_decision,
        "regime": regime,
        "regime_code": regime_info.get("regime_code"),
        "regime_detail": regime_info.get("detail"),
        "regime_advice": regime_info.get("advice"),
        "playbook": regime_info.get("playbook"),
        "adx": regime_info.get("adx"),
        "efficiency": regime_info.get("efficiency"),
        "side": side,
        "score": round(score, 4),
        "confidence": round(min(1.0, abs(score) / max(effective_threshold, 1e-6)), 4),
        "success_rate": round(hit_rate, 4),
        "success_samples": int(hit_n),
        "success_note": gate_note,
        "recommend": bool(recommend),
        "price": price,
        "entry": round(entry, 8),
        "stop_loss": round(sl, 8),
        "take_profit": round(tp, 8),
        "atr": round(atr_v, 8),
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
