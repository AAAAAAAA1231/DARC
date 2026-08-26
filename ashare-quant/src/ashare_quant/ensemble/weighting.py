"""Dynamic ensemble: rolling out-of-sample method performance → weights."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import AppConfig, EnsembleConfig
from ..signals.methods import method_scores


def softmax(x: np.ndarray, temperature: float) -> np.ndarray:
    z = np.asarray(x, dtype=float) / max(temperature, 1e-6)
    z = z - np.nanmax(z, axis=-1, keepdims=True)
    e = np.exp(np.clip(z, -20, 20))
    s = e.sum(axis=-1, keepdims=True)
    s = np.where(s <= 0, 1.0, s)
    return e / s


def method_proxy_returns(scores: pd.DataFrame, fwd_ret: pd.Series) -> pd.DataFrame:
    """Next-session return attributed to today's score (long-only clip)."""
    lagged_fwd = fwd_ret.shift(-1)
    pos = scores.clip(lower=0.0)
    return pos.mul(lagged_fwd, axis=0)


def project_weights(raw: np.ndarray, min_w: float, max_w: float) -> np.ndarray:
    """Simplex projection with per-method floor and cap."""
    w = np.asarray(raw, dtype=float)
    n = len(w)
    if n == 0:
        return w
    if not np.isfinite(w).all() or w.sum() <= 0:
        w = np.full(n, 1.0 / n)
    else:
        w = np.maximum(w, 0.0)
        w = w / w.sum()
    max_w = min(max_w, 1.0)
    min_w = max(0.0, min_w)
    if n * min_w > 1.0:
        return np.full(n, 1.0 / n)
    for _ in range(n + 3):
        w = np.clip(w, min_w, max_w)
        deficit = 1.0 - w.sum()
        if abs(deficit) < 1e-12:
            break
        if deficit > 0:
            room = max_w - w
            mask = room > 1e-12
            if not mask.any():
                break
            w[mask] += deficit * room[mask] / room[mask].sum()
        else:
            spare = w - min_w
            mask = spare > 1e-12
            if not mask.any():
                break
            w[mask] += deficit * spare[mask] / spare[mask].sum()
    w = np.clip(w, min_w, max_w)
    s = w.sum()
    if s <= 0:
        return np.full(n, 1.0 / n)
    return w / s


def rolling_weights(method_rets: pd.DataFrame, cfg: EnsembleConfig) -> pd.DataFrame:
    """Exponentially weighted Sharpe → softmax weights with floors/caps.

    Uses decaying OOS proxy returns rather than a single in-sample fit, so a
    method that recently stopped working is automatically down-weighted.
    """
    methods = list(method_rets.columns)
    sharpe_cols = []
    for m in methods:
        r = method_rets[m]
        mu = r.ewm(halflife=cfg.half_life, min_periods=5, adjust=False).mean()
        sd = r.ewm(halflife=cfg.half_life, min_periods=5, adjust=False).std()
        sh = np.sqrt(252.0) * mu / sd.replace(0.0, np.nan)
        sh = sh.clip(lower=cfg.negative_sharpe_floor).fillna(0.0)
        sharpe_cols.append(sh.rename(m))
    S = pd.concat(sharpe_cols, axis=1)
    arr = S.to_numpy(dtype=float)
    w = softmax(arr, cfg.temperature)
    projected = np.vstack([project_weights(row, cfg.min_weight, cfg.max_weight) for row in w])
    return pd.DataFrame(projected, index=method_rets.index, columns=methods)


def blend(scores: dict[str, float], weights: dict[str, float]) -> float:
    num = 0.0
    den = 0.0
    for k, s in scores.items():
        w = float(weights.get(k, 0.0))
        num += w * float(s)
        den += w
    if den <= 0:
        return 0.0
    return float(np.clip(num / den, -1.0, 1.0))


def default_equal_weights(cfg: AppConfig) -> dict[str, float]:
    n = max(1, len(cfg.ensemble.methods))
    return {m.value: 1.0 / n for m in cfg.ensemble.methods}


def compute_ensemble_panel(
    bars: pd.DataFrame,
    cfg: AppConfig,
    params: dict | None = None,
) -> pd.DataFrame:
    """Per-symbol daily method scores, dynamic weights, blended score."""
    parts = []
    methods = [m.value for m in cfg.ensemble.methods]
    n_m = max(1, len(methods))
    equal = 1.0 / n_m
    for symbol, g in bars.groupby("symbol", sort=False):
        g = g.sort_values("date").reset_index(drop=True)
        sc = method_scores(g, cfg, params)
        fwd = g["close"].pct_change()
        proxy = method_proxy_returns(sc[methods], fwd)
        proxy.index = sc["date"]
        w = rolling_weights(proxy, cfg.ensemble)
        w = w.reindex(sc["date"]).ffill().fillna(equal)
        blended = (sc[methods].to_numpy() * w[methods].to_numpy()).sum(axis=1)
        sc = sc.copy()
        sc["ensemble"] = np.clip(blended, -1.0, 1.0)
        for m in methods:
            sc[f"w_{m}"] = w[m].to_numpy()
        sc["fwd_ret"] = fwd.shift(-1).to_numpy()
        parts.append(sc)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()
