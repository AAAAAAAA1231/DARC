"""After-cost performance metrics. Emphasize drawdown and stability, not peak return."""

from __future__ import annotations

import numpy as np
import pandas as pd


def max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = equity / peak.replace(0, np.nan) - 1.0
    return float(dd.min()) if len(dd) else 0.0


def sharpe(returns: pd.Series, periods: int = 252) -> float:
    r = returns.dropna()
    if len(r) < 5:
        return 0.0
    sd = float(r.std())
    if sd <= 1e-12:
        return 0.0
    return float(np.sqrt(periods) * r.mean() / sd)


def sortino(returns: pd.Series, periods: int = 252) -> float:
    r = returns.dropna()
    downside = r[r < 0]
    if len(r) < 5 or len(downside) == 0:
        return 0.0
    dd = float(downside.std())
    if dd <= 1e-12:
        return 0.0
    return float(np.sqrt(periods) * r.mean() / dd)


def calmar(total_return: float, mdd: float, years: float) -> float:
    if years <= 0 or mdd >= 0:
        return 0.0
    cagr = (1.0 + total_return) ** (1.0 / years) - 1.0 if total_return > -1 else -1.0
    return float(cagr / abs(mdd))


def hit_rate(trade_pnl: pd.Series) -> float:
    if trade_pnl.empty:
        return 0.0
    return float((trade_pnl > 0).mean())


def summarize_equity(equity: pd.Series, trades: pd.DataFrame | None = None) -> dict:
    equity = equity.astype(float).dropna()
    if equity.empty:
        return {
            "total_return": 0.0,
            "sharpe": 0.0,
            "sortino": 0.0,
            "max_drawdown": 0.0,
            "calmar": 0.0,
            "vol": 0.0,
            "days": 0,
            "n_trades": 0,
            "hit_rate": 0.0,
            "avg_turnover": 0.0,
            "robust_score": -999.0,
        }
    rets = equity.pct_change().fillna(0.0)
    mdd = max_drawdown(equity)
    total = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    years = max(len(equity) / 252.0, 1e-6)
    n_trades = int(len(trades)) if trades is not None else 0
    hr = hit_rate(trades["pnl"]) if trades is not None and "pnl" in trades.columns and n_trades else 0.0
    turnover = 0.0
    if trades is not None and "notional" in trades.columns and n_trades:
        turnover = float(trades["notional"].abs().sum() / (equity.mean() * max(len(equity), 1)))
    sh = sharpe(rets)
    robust = sh - 0.9 * abs(mdd) * 10.0 - 0.15 * turnover  # penalize DD and churn
    return {
        "total_return": total,
        "sharpe": sh,
        "sortino": sortino(rets),
        "max_drawdown": mdd,
        "calmar": calmar(total, mdd, years),
        "vol": float(rets.std() * np.sqrt(252)),
        "days": int(len(equity)),
        "n_trades": n_trades,
        "hit_rate": hr,
        "avg_turnover": turnover,
        "robust_score": float(robust),
        "end_equity": float(equity.iloc[-1]),
        "start_equity": float(equity.iloc[0]),
    }
