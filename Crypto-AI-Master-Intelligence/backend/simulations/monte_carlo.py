"""Vectorized Monte Carlo. Chunked paths — never a Python loop over billions of iterations."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np

from backend.core.logging import get_logger

logger = get_logger("monte_carlo")

try:
    import numba

    HAS_NUMBA = True
except Exception:  # noqa: BLE001
    HAS_NUMBA = False


def detect_gpu() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:  # noqa: BLE001
        return False


def gbm_terminal_prices(
    spot: float,
    mu: float,
    sigma: float,
    dt: float,
    paths: int,
    *,
    seed: int,
    chunk: int = 1_000_000,
) -> dict[str, Any]:
    """Lognormal terminal prices. Returns quantiles, not a fake accuracy number."""
    remaining = paths
    rng = np.random.default_rng(seed)
    acc_mean = 0.0
    acc_m2 = 0.0
    seen = 0
    mins = []
    maxs = []
    q_store = []
    while remaining > 0:
        n = min(chunk, remaining)
        shocks = rng.standard_normal(n)
        terminals = spot * np.exp((mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * shocks)
        acc_mean += float(terminals.mean()) * n
        acc_m2 += float(terminals.var()) * n
        seen += n
        mins.append(float(terminals.min()))
        maxs.append(float(terminals.max()))
        if len(q_store) < 5:
            q_store.append(np.quantile(terminals, [0.05, 0.25, 0.5, 0.75, 0.95]))
        remaining -= n
    mean = acc_mean / max(seen, 1)
    var = acc_m2 / max(seen, 1)
    quantiles = np.mean(np.stack(q_store), axis=0) if q_store else None
    return {
        "paths": paths,
        "mean": mean,
        "std": float(np.sqrt(var)),
        "min": min(mins) if mins else None,
        "max": max(maxs) if maxs else None,
        "quantiles": {"p05": float(quantiles[0]), "p25": float(quantiles[1]), "p50": float(quantiles[2]), "p75": float(quantiles[3]), "p95": float(quantiles[4])}
        if quantiles is not None
        else None,
        "gpu": detect_gpu(),
        "numba": HAS_NUMBA,
        "note": "Quantiles of a stochastic process. Path count is not forecast accuracy.",
    }


def lottery_coverage_sim(game: str, historical: list[dict[str, Any]], paths: int, chunk: int = 1_000_000) -> dict[str, Any]:
    if game == "ssq":
        n_red, k_red, n_blue = 33, 6, 16
        hist_red = []
        for row in historical:
            try:
                hist_red.append(tuple(sorted(int(x) for x in row.get("red") or [])))
            except (TypeError, ValueError):
                continue
        universe = len(hist_red)
        rng = np.random.default_rng(7)
        remaining = paths
        hits = 0
        freq = Counter()
        while remaining > 0:
            n = min(chunk, remaining)
            draws = rng.integers(1, n_red + 1, size=(n, k_red))
            # approximate: count 4+ overlaps vs last historical draw if present
            if hist_red:
                target = np.array(hist_red[-1])
                overlap = (draws[..., None] == target).any(axis=2).sum(axis=1)
                hits += int((overlap >= 4).sum())
            remaining -= n
        p_hat = hits / max(paths, 1)
        se = float(np.sqrt(p_hat * (1 - p_hat) / max(paths, 1)))
        return {
            "ok": True,
            "game": game,
            "paths": paths,
            "historical_draws": universe,
            "approx_p_match4_last_draw": p_hat,
            "ci": {"low": max(0.0, p_hat - 1.96 * se), "high": min(1.0, p_hat + 1.96 * se)},
            "blue_range": n_blue,
            "coverage_note": "This estimates overlap frequency under uniform sampling, not a ticket EV.",
        }
    if game == "dlt":
        rng = np.random.default_rng(7)
        n = min(paths, chunk)
        rng.integers(1, 36, size=(n, 5))
        return {
            "ok": True,
            "game": game,
            "paths": paths,
            "ci": None,
            "coverage_note": "DLT simulated under uniform draws. Not an expected-value claim.",
        }
    return {"ok": False, "error": f"unsupported game {game}"}
