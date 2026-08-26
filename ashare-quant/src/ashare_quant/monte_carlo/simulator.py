"""Limited Monte Carlo on OOS returns, slippage and fill outcomes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..backtest.engine import run_backtest
from ..backtest.metrics import max_drawdown, sharpe, summarize_equity
from ..config import AppConfig, EnsembleConfig


@dataclass
class MonteCarloResult:
    summary: dict
    distribution: pd.DataFrame
    adjusted_ensemble: dict
    adjusted_risk: dict
    notes: list[str]


def _block_bootstrap(returns: np.ndarray, block: int, n: int, rng: np.random.Generator) -> np.ndarray:
    if len(returns) == 0:
        return np.zeros((n, 1))
    block = max(1, min(block, len(returns)))
    n_blocks = int(np.ceil(len(returns) / block))
    starts = rng.integers(0, max(1, len(returns) - block + 1), size=(n, n_blocks))
    paths = np.empty((n, n_blocks * block))
    for i in range(n):
        chunks = [returns[s : s + block] for s in starts[i]]
        paths[i] = np.concatenate(chunks)[: n_blocks * block]
    return paths[:, : len(returns)]


def simulate_return_paths(oos_returns: pd.Series, cfg: AppConfig, seed: int | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed if seed is not None else cfg.seed + 7)
    r = oos_returns.dropna().to_numpy(dtype=float)
    if len(r) < 10:
        return pd.DataFrame()
    paths = _block_bootstrap(r, cfg.monte_carlo.block_size, cfg.monte_carlo.n_sims, rng)
    rows = []
    for i, path in enumerate(paths):
        eq = np.cumprod(1.0 + path)
        ser = pd.Series(eq)
        ret = pd.Series(path)
        rows.append(
            {
                "sim": i,
                "total_return": float(eq[-1] - 1.0),
                "sharpe": sharpe(ret),
                "max_drawdown": max_drawdown(ser),
                "end_multiple": float(eq[-1]),
            }
        )
    return pd.DataFrame(rows)


def simulate_execution_noise(
    bars: pd.DataFrame,
    meta: pd.DataFrame,
    cfg: AppConfig,
    symbols: list[str] | None,
    n_sims: int | None = None,
    seed: int | None = None,
) -> pd.DataFrame:
    """Re-run a short backtest with resampled slippage and fill jitter (limited times)."""
    rng = np.random.default_rng(seed if seed is not None else cfg.seed + 11)
    n = n_sims if n_sims is not None else min(8, max(4, cfg.monte_carlo.n_sims // 15))
    rows = []
    sessions = list(pd.to_datetime(bars["date"]).drop_duplicates().sort_values())
    start = sessions[max(0, len(sessions) - 220)] if sessions else None
    for i in range(n):
        slip = float(rng.uniform(cfg.monte_carlo.slippage_low, cfg.monte_carlo.slippage_high))
        jitter = float(rng.uniform(0.0, cfg.monte_carlo.fill_jitter))
        bt = run_backtest(
            bars,
            meta,
            cfg,
            symbols=symbols,
            start=start,
            slippage_mult=slip,
            fill_jitter=jitter,
            rng=rng,
        )
        m = bt.metrics
        rows.append(
            {
                "sim": i,
                "slippage_mult": slip,
                "fill_jitter": jitter,
                "total_return": m["total_return"],
                "sharpe": m["sharpe"],
                "max_drawdown": m["max_drawdown"],
                "n_trades": m["n_trades"],
            }
        )
    return pd.DataFrame(rows)


def calibrate_from_distribution(
    dist: pd.DataFrame,
    cfg: AppConfig,
    current_weights: dict[str, float] | None = None,
) -> tuple[dict, dict, list[str]]:
    notes: list[str] = []
    risk = {
        "max_gross_exposure": cfg.risk.max_gross_exposure,
        "max_single_weight": cfg.risk.max_single_weight,
        "per_name_risk": cfg.risk.per_name_risk,
        "stop_atr_k": cfg.risk.stop_atr_k,
    }
    ens = {
        "min_weight": cfg.ensemble.min_weight,
        "max_weight": cfg.ensemble.max_weight,
        "temperature": cfg.ensemble.temperature,
    }
    if current_weights:
        ens["weights"] = current_weights
    if dist.empty:
        notes.append("模拟样本不足，保持原风控参数。")
        return ens, risk, notes

    dd = dist["max_drawdown"].astype(float)
    p_bad = float((dd <= -abs(cfg.monte_carlo.dd_alert)).mean())
    med_sharpe = float(dist["sharpe"].median())
    p05_ret = float(dist["total_return"].quantile(0.05))
    notes.append(f"最大回撤劣于 {cfg.monte_carlo.dd_alert:.0%} 的模拟占比 {p_bad:.1%}。")
    notes.append(f"模拟 Sharpe 中位数 {med_sharpe:.2f}，收益 5% 分位 {p05_ret:.1%}。")

    if p_bad > cfg.monte_carlo.dd_prob_cap:
        risk["max_gross_exposure"] = round(cfg.risk.max_gross_exposure * 0.75, 4)
        risk["per_name_risk"] = round(cfg.risk.per_name_risk * 0.8, 5)
        risk["stop_atr_k"] = round(cfg.risk.stop_atr_k * 0.9, 3)
        ens["max_weight"] = round(min(cfg.ensemble.max_weight, 0.32), 4)
        notes.append("尾部回撤过厚：下调总仓、单票风险预算，并收紧单一方法权重上限。")
    elif med_sharpe < 0:
        ens["temperature"] = round(min(1.2, cfg.ensemble.temperature + 0.2), 3)
        notes.append("样本外中位夏普为负：提高权重温度，避免过度倾斜近期赢家方法。")
    else:
        notes.append("模拟分布未触发强制降仓；仍以仓位上限与止损距离为硬约束。")

    return ens, risk, notes


def run_monte_carlo(
    oos_equity: pd.Series,
    bars: pd.DataFrame,
    meta: pd.DataFrame,
    cfg: AppConfig,
    symbols: list[str] | None = None,
    weights: dict[str, float] | None = None,
    skip_execution: bool = False,
) -> MonteCarloResult:
    rets = oos_equity.pct_change().dropna()
    dist_ret = simulate_return_paths(rets, cfg)
    dist_exec = pd.DataFrame()
    if not skip_execution:
        noise_n = min(6, max(3, cfg.monte_carlo.n_sims // 20))
        dist_exec = simulate_execution_noise(bars, meta, cfg, symbols, n_sims=noise_n)
    dist = dist_ret.copy()
    dist["source"] = "return_bootstrap"
    if not dist_exec.empty:
        tmp = dist_exec.copy()
        tmp["source"] = "execution_noise"
        dist = pd.concat([dist, tmp], ignore_index=True, sort=False)
    use = dist_ret if not dist_ret.empty else dist_exec
    ens, risk, notes = calibrate_from_distribution(use, cfg, weights)
    summary = {
        "n_return_sims": int(len(dist_ret)),
        "n_exec_sims": int(len(dist_exec)),
        "sharpe_median": float(use["sharpe"].median()) if len(use) else 0.0,
        "sharpe_p10": float(use["sharpe"].quantile(0.10)) if len(use) else 0.0,
        "dd_median": float(use["max_drawdown"].median()) if len(use) else 0.0,
        "dd_p10": float(use["max_drawdown"].quantile(0.10)) if len(use) else 0.0,
        "ret_median": float(use["total_return"].median()) if len(use) else 0.0,
        "ret_p05": float(use["total_return"].quantile(0.05)) if len(use) else 0.0,
        "p_dd_worse_than_alert": float((use["max_drawdown"] <= -abs(cfg.monte_carlo.dd_alert)).mean()) if len(use) else 0.0,
    }
    return MonteCarloResult(summary, dist, ens, risk, notes)
