from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .methods import METHODS, all_score_matrix, last_signals, method_names
from .data_source import Bars


@dataclass
class EnsembleResult:
    score: float
    confidence: float
    agreement: float
    direction: str
    horizon_days: int
    contributions: list[dict]


def prior_weights() -> np.ndarray:
    """Literature-style priors: trend + A-share oscillators slightly higher."""
    boost = {
        "kdj_j": 1.25,
        "ma_cross_5_20": 1.15,
        "macd_hist": 1.15,
        "bias": 1.1,
        "vol_price": 1.1,
        "rsi_mr": 1.05,
        "donchian": 1.05,
        "hv_revert": 0.8,
        "gap": 0.85,
    }
    w = np.array([boost.get(m.name, 1.0) for m in METHODS], dtype=np.float64)
    return w / w.sum()


def combine_signals(
    signals: list[dict],
    weights: np.ndarray,
    horizon_days: int = 5,
) -> EnsembleResult:
    scores = np.array([s["score"] for s in signals], dtype=np.float64)
    conf = np.array([s["confidence"] for s in signals], dtype=np.float64)
    w = np.asarray(weights, dtype=np.float64)
    w = np.maximum(w, 0)
    w = w / w.sum() if w.sum() > 0 else np.full_like(w, 1.0 / len(w))
    weighted = w * np.clip(conf, 0.05, 1.0)
    denom = float(weighted.sum())
    score = float((weighted * scores).sum() / denom) if denom else 0.0
    signs = np.sign(scores)
    same = float(np.mean(signs == np.sign(score))) if score != 0 else float(np.mean(np.abs(scores) < 0.15))
    agreement = float(np.clip(same, 0, 1))
    confidence = float(np.clip(abs(score) * (0.55 + 0.45 * agreement), 0, 1))
    if score > 0.18:
        direction = "上涨"
    elif score < -0.18:
        direction = "下跌"
    else:
        direction = "震荡"
    contrib = []
    for sig, wi in zip(signals, w.tolist()):
        contrib.append(
            {
                **sig,
                "weight": round(float(wi), 6),
                "contribution": round(float(wi * sig["score"] * max(sig["confidence"], 0.05)), 6),
            }
        )
    contrib.sort(key=lambda x: abs(x["contribution"]), reverse=True)
    return EnsembleResult(
        score=round(score, 4),
        confidence=round(confidence, 4),
        agreement=round(agreement, 4),
        direction=direction,
        horizon_days=horizon_days,
        contributions=contrib,
    )


def apply_correction(prior: np.ndarray, posterior: np.ndarray, ic: np.ndarray) -> np.ndarray:
    """Blend MC posterior, information coefficient, and prior."""
    reliability = 0.5 + 0.5 * np.tanh(np.nan_to_num(ic, nan=0.0) * 8.0)
    blended = np.maximum(prior, 1e-8) ** 0.25 * np.maximum(posterior, 1e-8) ** 0.55 * np.maximum(reliability, 0.05)
    return blended / blended.sum()


def ensemble_from_bars(bars: Bars, weights: np.ndarray, horizon_days: int = 5) -> EnsembleResult:
    return combine_signals(last_signals(bars), weights, horizon_days=horizon_days)


def aligned_method_returns(bars_list: list[Bars], horizon: int = 5, cost: float = 0.0008) -> tuple[np.ndarray, np.ndarray]:
    """
    Build method daily strategy returns (equal-stock average).
    Position is clipped score at t, applied to next-day return (A-share T+1 style).
    """
    names = method_names()
    date_to_ret: dict[str, list[np.ndarray]] = {}
    for bars in bars_list:
        if len(bars) < horizon + 60:
            continue
        _, matrix = all_score_matrix(bars)
        close = bars.close
        fwd = np.zeros(len(close))
        fwd[:-horizon] = close[horizon:] / close[:-horizon] - 1.0
        pos = np.clip(matrix, -1.0, 1.0)
        # T+1: today's signal trades tomorrow's move, held `horizon` days / horizon
        daily = pos[:-1] * (close[1:] / close[:-1] - 1.0)[:, None]
        turnover = np.abs(pos[1:] - pos[:-1])
        daily -= turnover * cost
        for i, day in enumerate(bars.dates[1:]):
            date_to_ret.setdefault(str(day), []).append(daily[i])
    if not date_to_ret:
        return np.zeros(len(names)), np.eye(len(names)) * 1e-6
    keys = sorted(date_to_ret)
    panel = np.vstack([np.mean(np.stack(date_to_ret[k], axis=0), axis=0) for k in keys])
    mu = panel.mean(axis=0)
    cov = np.cov(panel, rowvar=False)
    if cov.ndim == 0:
        cov = np.array([[float(cov)]])
    cov = np.nan_to_num(cov, nan=0.0)
    cov = 0.5 * (cov + cov.T) + np.eye(len(names)) * 1e-8
    return mu.astype(np.float64), cov.astype(np.float64)


def information_coefficients(bars_list: list[Bars], horizon: int = 5) -> np.ndarray:
    ics = []
    for bars in bars_list:
        if len(bars) < horizon + 80:
            continue
        _, matrix = all_score_matrix(bars)
        fwd = np.zeros(len(bars.close))
        fwd[:-horizon] = bars.close[horizon:] / bars.close[:-horizon] - 1.0
        col_ics = []
        for j in range(matrix.shape[1]):
            x = matrix[:-horizon, j]
            y = fwd[:-horizon]
            mask = np.isfinite(x) & np.isfinite(y)
            if mask.sum() < 40 or np.std(x[mask]) < 1e-12 or np.std(y[mask]) < 1e-12:
                col_ics.append(0.0)
            else:
                col_ics.append(float(np.corrcoef(x[mask], y[mask])[0, 1]))
        ics.append(col_ics)
    if not ics:
        return np.zeros(len(method_names()))
    return np.nanmean(np.asarray(ics), axis=0)
