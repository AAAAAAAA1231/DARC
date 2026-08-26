"""Paper-trading replay: same T+1/cost/risk engine, marked as pre-live only."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..backtest.engine import BacktestResult, run_backtest
from ..config import AppConfig


@dataclass
class PaperRun:
    result: BacktestResult
    window: tuple
    disclaimer: str


DISCLAIMER = (
    "模拟盘不是实盘。成交、滑点与涨跌停排队均被简化；正式资金使用前必须经过更长样本外与模拟盘验证。"
    "本系统输出概率信号与风险区间，不构成投资建议。"
)


def run_paper(
    bars: pd.DataFrame,
    meta: pd.DataFrame,
    cfg: AppConfig,
    symbols: list[str] | None = None,
    days: int | None = None,
) -> PaperRun:
    days = days or cfg.paper.days
    sessions = list(pd.to_datetime(bars["date"]).drop_duplicates().sort_values())
    start = sessions[max(0, len(sessions) - max(days, 30) - cfg.signals.lookback)]
    end = sessions[-1]
    bt = run_backtest(bars, meta, cfg, symbols=symbols, start=start, end=end)
    return PaperRun(result=bt, window=(start, end), disclaimer=DISCLAIMER)
