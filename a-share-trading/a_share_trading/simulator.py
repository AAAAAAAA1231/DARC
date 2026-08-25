from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from multiprocessing import get_context

import numpy as np
from numba import njit

from . import config
from .methods import METHODS


@dataclass
class SimResult:
    n_sims: int
    elapsed_sec: float
    best_sharpe: float
    best_return: float
    best_vol: float
    prior_weights: dict[str, float]
    posterior_weights: dict[str, float]
    ic: dict[str, float]
    corrected_weights: dict[str, float]
    method_mu: dict[str, float]
    sims_per_sec: float


def _mean_correlation(cov: np.ndarray) -> float:
    n = cov.shape[0]
    sig = np.sqrt(np.clip(np.diag(cov), 1e-18, None))
    corr = cov / np.outer(sig, sig)
    mask = np.triu(np.ones((n, n), dtype=bool), k=1)
    vals = corr[mask]
    vals = vals[np.isfinite(vals)]
    if vals.size == 0:
        return 0.15
    return float(np.clip(np.mean(vals), -0.2, 0.85))


@njit(fastmath=True)
def _fast_mc(n_sims: int, mu: np.ndarray, var: np.ndarray, rho: float, seed: int):
    np.random.seed(seed)
    m = mu.shape[0]
    w = np.ones(m) / m
    credit = np.zeros(m)
    mass = 0.0
    best = -1e18
    best_w = w.copy()
    sig = np.sqrt(var)
    for t in range(n_sims):
        if t % 96 == 0:
            s = 0.0
            for i in range(m):
                u = np.random.random()
                if u < 1e-18:
                    u = 1e-18
                w[i] = -np.log(u)
                s += w[i]
            for i in range(m):
                w[i] /= s
        else:
            k = np.random.randint(0, m)
            w[k] *= np.exp(np.random.normal(0.0, 0.14))
            s = 0.0
            for i in range(m):
                s += w[i]
            for i in range(m):
                w[i] /= s
        ret = 0.0
        diag = 0.0
        cs = 0.0
        for i in range(m):
            wi = w[i]
            ret += wi * mu[i]
            diag += wi * wi * var[i]
            cs += wi * sig[i]
        port_var = (1.0 - rho) * diag + rho * cs * cs
        sc = ret / np.sqrt(port_var + 1e-18)
        if sc > best:
            best = sc
            for i in range(m):
                best_w[i] = w[i]
        if sc > 0.0:
            mass += sc
            for i in range(m):
                credit[i] += sc * w[i]
    return best, best_w, credit, mass, n_sims


def _worker(payload: tuple) -> dict:
    mu, var, rho, n_sims, seed = payload
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    best, best_w, credit, mass, done = _fast_mc(int(n_sims), mu, var, float(rho), int(seed))
    return {
        "best_sharpe": float(best),
        "best_w": np.asarray(best_w, dtype=np.float64),
        "credit": np.asarray(credit, dtype=np.float64),
        "credit_mass": float(mass),
        "done": int(done),
    }


def _full_sharpe(w: np.ndarray, mu: np.ndarray, cov: np.ndarray) -> tuple[float, float, float]:
    ret = float(w @ mu)
    vol = float(np.sqrt(max(w @ cov @ w, 1e-18)))
    return ret / vol, ret, vol


def run_monte_carlo(
    mu: np.ndarray,
    cov: np.ndarray,
    n_sims: int = config.N_SIMS_DELIVERY,
    batch: int = config.SIM_BATCH,
    seed: int = 42,
    workers: int | None = None,
    progress_cb=None,
) -> dict:
    del batch  # kept for CLI compatibility; inner loop is 1-sim granular
    workers = workers or max(1, os.cpu_count() or 1)
    workers = max(1, min(workers, int(n_sims)))
    mu = np.asarray(mu, dtype=np.float64).reshape(-1)
    cov = np.asarray(cov, dtype=np.float64)
    var = np.clip(np.diag(cov), 1e-12, None)
    rho = _mean_correlation(cov)
    chunks = [n_sims // workers] * workers
    chunks[-1] += n_sims - sum(chunks)
    payloads = [
        (mu, var, rho, chunks[i], seed + 10007 * i)
        for i in range(workers)
        if chunks[i] > 0
    ]
    _fast_mc(256, mu, var, rho, 0)  # warmup compile
    t0 = time.perf_counter()
    if len(payloads) == 1:
        parts = [_worker(payloads[0])]
    else:
        ctx = get_context("fork")
        with ctx.Pool(len(payloads)) as pool:
            parts = pool.map(_worker, payloads)
    elapsed = time.perf_counter() - t0
    best = max(parts, key=lambda p: p["best_sharpe"])
    credit = np.sum([p["credit"] for p in parts], axis=0)
    mass = sum(p["credit_mass"] for p in parts)
    posterior = credit / mass if mass > 0 else np.full_like(credit, 1.0 / len(credit))
    posterior = np.maximum(posterior, 0)
    posterior = posterior / posterior.sum()
    best_ret, best_vol = _full_sharpe(best["best_w"], mu, cov)[1:]
    best_sharpe_full = _full_sharpe(best["best_w"], mu, cov)[0]
    if progress_cb:
        progress_cb(n_sims, elapsed)
    return {
        "n_sims": int(sum(p["done"] for p in parts)),
        "elapsed_sec": round(elapsed, 3),
        "best_sharpe": float(best_sharpe_full),
        "best_return": float(best_ret),
        "best_vol": float(best_vol),
        "best_weights": best["best_w"],
        "posterior_weights": posterior,
        "sims_per_sec": float(n_sims / elapsed) if elapsed else 0.0,
        "approx_best_sharpe": float(best["best_sharpe"]),
        "mean_corr": rho,
    }


def save_progress(n_done: int, n_total: int, extra: dict | None = None) -> None:
    payload = {
        "n_done": n_done,
        "n_total": n_total,
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if extra:
        payload.update(extra)
    config.SIM_PROGRESS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
