"""Walk-forward validation with a small robust-score grid (not in-sample max return)."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product

import pandas as pd

from ..config import AppConfig
from .engine import BacktestResult, run_backtest
from .metrics import summarize_equity


@dataclass
class WalkForwardResult:
    oos_equity: pd.Series
    folds: pd.DataFrame
    chosen_params: list[dict]
    oos_metrics: dict
    combined: BacktestResult | None


def _grid(cfg: AppConfig) -> list[dict]:
    cap = max(1, cfg.walkforward.param_grid_cap)
    trend_fast = [8, 12]
    trend_slow = [36, 48]
    mom = [10, 20]
    zwin = [15, 20]
    brk = [1.6, 2.0]
    rs = [20]
    combos = []
    for fast, slow, roc, zw, k, rsw in product(trend_fast, trend_slow, mom, zwin, brk, rs):
        if fast >= slow:
            continue
        combos.append(
            {
                "trend": {"fast": fast, "slow": slow, "adx_window": 14},
                "momentum": {"roc_window": roc, "rsi_window": 14},
                "mean_reversion": {"z_window": zw, "entry_z": 1.2},
                "volatility": {"atr_window": 14, "breakout_k": k},
                "relative_strength": {"window": rsw},
            }
        )
        if len(combos) >= cap:
            break
    return combos


def _robust(metrics: dict) -> float:
    return float(metrics.get("robust_score", -999.0))


def walk_forward(
    bars: pd.DataFrame,
    meta: pd.DataFrame,
    cfg: AppConfig,
    symbols: list[str] | None = None,
) -> WalkForwardResult:
    sessions = list(pd.to_datetime(bars["date"]).drop_duplicates().sort_values())
    train_n = cfg.walkforward.train_days
    test_n = cfg.walkforward.test_days
    step = cfg.walkforward.step_days
    if len(sessions) < train_n + test_n:
        # Short sample: single fold using last 25% as OOS
        cut = int(len(sessions) * (1.0 - cfg.walkforward.inner_validation_frac))
        train_n = max(40, cut)
        test_n = max(20, len(sessions) - train_n)
        step = test_n

    grid = _grid(cfg)
    folds = []
    chosen = []
    oos_parts: list[pd.Series] = []
    last_bt: BacktestResult | None = None

    start_i = 0
    fold_id = 0
    while start_i + train_n + 10 < len(sessions):
        train_slice = sessions[start_i : start_i + train_n]
        test_end = min(len(sessions), start_i + train_n + test_n)
        test_slice = sessions[start_i + train_n : test_end]
        if len(test_slice) < 10:
            break
        val_cut = train_slice[int(len(train_slice) * (1.0 - cfg.walkforward.inner_validation_frac))]
        best_p = grid[0]
        best_score = -1e18
        for p in grid:
            bt = run_backtest(
                bars,
                meta,
                cfg,
                params=p,
                symbols=symbols,
                start=train_slice[0],
                end=val_cut,
            )
            score = _robust(bt.metrics)
            if cfg.walkforward.selection != "robust":
                score = bt.metrics.get("sharpe", score)
            if score > best_score:
                best_score = score
                best_p = p
        oos = run_backtest(
            bars,
            meta,
            cfg,
            params=best_p,
            symbols=symbols,
            start=train_slice[0],  # need history for indicators; metrics sliced below
            end=test_slice[-1],
        )
        eq = oos.equity
        if eq.empty:
            start_i += step
            continue
        # Keep only the test window for OOS concatenation (true walk-forward).
        test_eq = eq[(eq.index >= test_slice[0]) & (eq.index <= test_slice[-1])]
        if test_eq.empty:
            start_i += step
            continue
        # Stitch: rebase to previous OOS end
        if oos_parts:
            prev_end = float(oos_parts[-1].iloc[-1])
            test_eq = test_eq / float(test_eq.iloc[0]) * prev_end
        else:
            test_eq = test_eq / float(test_eq.iloc[0]) * cfg.risk.initial_cash
        oos_parts.append(test_eq)
        fold_metrics = summarize_equity(test_eq)
        folds.append(
            {
                "fold": fold_id,
                "train_start": train_slice[0].date(),
                "train_end": train_slice[-1].date(),
                "test_start": test_slice[0].date(),
                "test_end": test_slice[-1].date(),
                "chosen_fast": best_p["trend"]["fast"],
                "chosen_slow": best_p["trend"]["slow"],
                "chosen_roc": best_p["momentum"]["roc_window"],
                "val_robust": best_score,
                **{f"oos_{k}": v for k, v in fold_metrics.items() if k in ("sharpe", "max_drawdown", "total_return", "robust_score")},
            }
        )
        chosen.append(best_p)
        last_bt = oos
        fold_id += 1
        start_i += step
        if fold_id >= 8:
            break

    if not oos_parts:
        bt = run_backtest(bars, meta, cfg, symbols=symbols)
        return WalkForwardResult(bt.equity, pd.DataFrame(), [grid[0]], bt.metrics, bt)

    oos_equity = pd.concat(oos_parts).sort_index()
    oos_equity = oos_equity[~oos_equity.index.duplicated(keep="last")]
    metrics = summarize_equity(oos_equity)
    return WalkForwardResult(oos_equity, pd.DataFrame(folds), chosen, metrics, last_bt)
