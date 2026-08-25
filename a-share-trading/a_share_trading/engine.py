from __future__ import annotations

import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Any

import numpy as np

from . import config
from .data_source import (
    Bars,
    Stock,
    fetch_all_klines,
    fetch_universe,
    load_or_make_bars,
    load_universe,
    synthesize_bars,
)
from .ensemble import (
    apply_correction,
    aligned_method_returns,
    combine_signals,
    information_coefficients,
    prior_weights,
)
from .methods import METHODS, last_signals, method_names
from .risk import build_risk_plan
from .simulator import run_monte_carlo, save_progress


def _json_dump(path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _worker_predict(payload: tuple[Stock, np.ndarray, int]) -> dict[str, Any]:
    stock, weights, horizon = payload
    bars = load_or_make_bars(stock, allow_synthetic=True)
    signals = last_signals(bars)
    ens = combine_signals(signals, weights, horizon_days=horizon)
    plan = build_risk_plan(stock, bars, ens)
    spark = [round(float(x), 4) for x in bars.close[-60:]]
    return {
        "code": stock.code,
        "name": stock.name,
        "symbol": stock.symbol,
        "exchange": stock.exchange,
        "board": stock.board,
        "last": plan.entry,
        "change_pct": round(float(stock.change_pct), 3),
        "pe": stock.pe,
        "pb": stock.pb,
        "mktcap": stock.mktcap,
        "direction": ens.direction,
        "score": ens.score,
        "confidence": ens.confidence,
        "agreement": ens.agreement,
        "side": plan.side,
        "take_profit": plan.take_profit,
        "stop_loss": plan.stop_loss,
        "reward_risk": plan.reward_risk,
        "atr": plan.atr,
        "limit_pct": plan.limit_pct,
        "notes": plan.notes,
        "data_source": bars.source,
        "bars": len(bars),
        "spark": spark,
        "methods": ens.contributions[:12],
        "horizon_days": ens.horizon_days,
    }


def _calibration_bars(stocks: list[Stock], limit: int) -> list[Bars]:
    from .data_source import load_bars

    ranked = sorted(stocks, key=lambda s: (s.mktcap or 0), reverse=True)
    live: list[Bars] = []
    fallback: list[Bars] = []
    for stock in ranked:
        bars = load_bars(stock.symbol)
        if bars is not None and len(bars) >= config.MIN_BARS:
            live.append(bars)
        elif len(fallback) < limit:
            fallback.append(synthesize_bars(stock))
        if len(live) >= limit:
            break
    chosen = live[:limit]
    if len(chosen) < limit:
        chosen.extend(fallback[: limit - len(chosen)])
    if len(chosen) < 16:
        for stock in ranked[:16]:
            chosen.append(synthesize_bars(stock))
    return chosen[: max(limit, 16)]


def calibrate(
    stocks: list[Stock] | None = None,
    n_sims: int = config.N_SIMS_DELIVERY,
    sample_size: int = 240,
    workers: int | None = None,
) -> dict[str, Any]:
    stocks = stocks or load_universe()
    bars_list = _calibration_bars(stocks, sample_size)
    names = method_names()
    prior = prior_weights()
    print(f"[calibrate] computing method returns on {len(bars_list)} names, {len(names)} methods")
    mu, cov = aligned_method_returns(bars_list, horizon=config.HORIZON_DAYS, cost=config.COST_BPS / 10000.0)
    ic = information_coefficients(bars_list, horizon=config.HORIZON_DAYS)
    print(f"[calibrate] launching {n_sims:,} Monte Carlo weight simulations")
    save_progress(0, n_sims, {"stage": "running"})
    t0 = time.perf_counter()
    mc = run_monte_carlo(mu, cov, n_sims=n_sims, workers=workers)
    save_progress(mc["n_sims"], n_sims, {"stage": "done", "elapsed_sec": mc["elapsed_sec"]})
    posterior = np.asarray(mc["posterior_weights"], dtype=np.float64)
    corrected = apply_correction(prior, posterior, ic)
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_sims": mc["n_sims"],
        "elapsed_sec": mc["elapsed_sec"],
        "sims_per_sec": round(mc["sims_per_sec"], 1),
        "sample_size": len(bars_list),
        "horizon_days": config.HORIZON_DAYS,
        "best_sharpe": mc["best_sharpe"],
        "best_return": mc["best_return"],
        "best_vol": mc["best_vol"],
        "prior_weights": {n: round(float(w), 8) for n, w in zip(names, prior)},
        "posterior_weights": {n: round(float(w), 8) for n, w in zip(names, posterior)},
        "ic": {n: round(float(w), 8) for n, w in zip(names, ic)},
        "method_mu": {n: round(float(w), 8) for n, w in zip(names, mu)},
        "corrected_weights": {n: round(float(w), 8) for n, w in zip(names, corrected)},
        "methods": [
            {
                "name": n,
                "title": METHODS[i].title,
                "prior": round(float(prior[i]), 8),
                "ic": round(float(ic[i]), 8),
                "mu": round(float(mu[i]), 8),
                "posterior": round(float(posterior[i]), 8),
                "corrected": round(float(corrected[i]), 8),
            }
            for i, n in enumerate(names)
        ],
        "wall_clock_sec": round(time.perf_counter() - t0, 3),
        "disclaimer": "研究工具，不构成投资建议。回测与模拟均不能代表未来收益。",
    }
    _json_dump(config.CALIBRATION_PATH, payload)
    return payload


def load_weights() -> np.ndarray:
    names = method_names()
    if config.CALIBRATION_PATH.exists():
        raw = json.loads(config.CALIBRATION_PATH.read_text(encoding="utf-8"))
        table = raw.get("corrected_weights") or raw.get("posterior_weights")
        if table:
            return np.array([float(table.get(n, 0.0)) for n in names], dtype=np.float64)
    return prior_weights()


def predict_all(stocks: list[Stock] | None = None, workers: int | None = None) -> list[dict[str, Any]]:
    import os

    stocks = stocks or load_universe()
    weights = load_weights()
    payloads = [(s, weights, config.HORIZON_DAYS) for s in stocks]
    workers = 1 if workers == 1 else (workers or os.cpu_count() or 1)
    if workers == 1 or len(payloads) < 8:
        rows = [_worker_predict(p) for p in payloads]
    else:
        rows = []
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_worker_predict, p) for p in payloads]
            for fut in as_completed(futs):
                rows.append(fut.result())
    rows.sort(key=lambda r: r["code"])
    payload = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "count": len(rows),
        "horizon_days": config.HORIZON_DAYS,
        "disclaimer": "研究工具，不构成投资建议。",
        "items": rows,
    }
    _json_dump(config.PREDICTIONS_PATH, payload)
    return rows


def ensure_universe(force: bool = False) -> list[Stock]:
    return fetch_universe(force=force)


def ensure_bars(limit: int | None = None, max_workers: int = 16) -> dict[str, int]:
    stocks = load_universe()
    return fetch_all_klines(stocks, limit=limit, max_workers=max_workers)
