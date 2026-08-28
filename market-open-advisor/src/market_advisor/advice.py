"""Turn simulation stats into a venue-level action. Not licensed investment advice."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from .markets import Market, session_label
from .model import FittedModel, SimulationStats


@dataclass
class Advice:
    market_key: str
    market_name: str
    exchange: str
    index_name: str
    symbol: str
    opened_at: str
    session: str
    last_close: float
    last_date: str
    spot: float | None
    change_pct: float | None
    action: str
    size_pct: int
    regime: str
    expected_return: float
    p_up: float
    p05: float
    p50: float
    p95: float
    sigma: float
    n_limit_sims: int
    n_verify_sims: int
    verify_error: float
    n_hist: int
    n_regime: int
    momentum_20: float
    vol_20: float
    data_source: str
    is_index: bool
    reasons: list[str]
    disclaimer: str
    stocks: list["Advice"] = field(default_factory=list)

    def to_dict(self) -> dict:
        payload = asdict(self)
        return payload


DISCLAIMER = (
    "本工具根据公开行情做量化研究，输出不是投资建议、不是收益承诺。"
    "股市有风险，交易需自负。数据来自交易所公开行情源，与同花顺展示的是同一套成交数据，"
    "并非同花顺终端授权接口。"
)

ACTION_LONG = "偏多"
ACTION_FLAT = "观望"
ACTION_SHORT = "偏空"


def decide_action(
    stats: SimulationStats, model: FittedModel, is_index: bool = True
) -> tuple[str, int, list[str]]:
    exp_r = stats.expected_return
    p_up = stats.p_up
    p05 = stats.p05
    vol = max(stats.sigma, 1e-8)
    edge = exp_r / vol
    reasons = [
        f"当前趋势状态为「{model.regime}」，从同类状态下的 {model.n_regime} 个历史交易日收益做条件自助抽样。",
        f"100亿次独立模拟的解析极限：期望日收益 {exp_r:.3%}，上涨概率 {p_up:.1%}，5%分位 {p05:.3%}。",
        f"20日动量 {model.momentum_20:.2%}，20日波动 {model.vol_20:.2%}，收盘相对 MA20 {(model.last_close / model.ma20 - 1):.2%}。",
    ]

    if exp_r > 0.0015 and p_up >= 0.54 and p05 > -0.035:
        action = ACTION_LONG
        size = int(max(10, min(60, round(18 * max(edge, 0.0) * 100))))
        reasons.append("期望收益为正且左尾可控，建议该市场指数相关仓位偏多、控制总仓。" if is_index else "期望收益为正且左尾可控，建议该股票偏多、控制单票仓位。")
    elif exp_r < -0.0015 and p_up <= 0.46:
        action = ACTION_SHORT
        size = int(max(0, min(40, round(12 * max(-edge, 0.0) * 100))))
        reasons.append("条件期望为负、上涨概率偏低，建议该市场以减仓或对冲为主，不做追空杠杆。" if is_index else "条件期望为负，建议该股票减仓或回避，不做追空杠杆。")
    else:
        action = ACTION_FLAT
        size = 0
        reasons.append("期望收益接近零或分位风险不对称，建议观望，等待状态切换。")

    if model.vol_20 > 0.025:
        size = int(round(size * 0.7))
        reasons.append("近20日波动偏高，仓位再打七折。")
    return action, size, reasons


def build_advice(
    market: Market,
    index_name: str,
    model: FittedModel,
    limit: SimulationStats,
    verify: SimulationStats,
    verify_error: float,
    opened_at: datetime,
    spot: float | None,
    change_pct: float | None,
    data_source: str,
    symbol: str = "",
    is_index: bool = True,
) -> Advice:
    action, size, reasons = decide_action(limit, model, is_index=is_index)
    if verify.n_sims:
        reasons.append(
            f"本次启动用 {verify.n_sims:,} 次流式蒙特卡洛核验，期望收益偏差 {verify_error:.2e}。"
        )
    if change_pct is not None:
        reasons.append(f"打开时刻现价涨跌 {change_pct:.2f}%。")
    reasons.append(f"行情源 {data_source}（交易所公开成交，与同花顺展示口径一致）。")
    return Advice(
        market_key=market.key,
        market_name=market.name,
        exchange=market.exchange,
        index_name=index_name,
        symbol=symbol,
        opened_at=opened_at.isoformat(timespec="seconds"),
        session=session_label(market, opened_at),
        last_close=model.last_close,
        last_date=model.last_date,
        spot=spot,
        change_pct=change_pct,
        action=action,
        size_pct=size,
        regime=model.regime,
        expected_return=limit.expected_return,
        p_up=limit.p_up,
        p05=limit.p05,
        p50=limit.p50,
        p95=limit.p95,
        sigma=limit.sigma,
        n_limit_sims=limit.n_sims,
        n_verify_sims=verify.n_sims,
        verify_error=verify_error,
        n_hist=model.n_hist,
        n_regime=model.n_regime,
        momentum_20=model.momentum_20,
        vol_20=model.vol_20,
        data_source=data_source,
        is_index=is_index,
        reasons=reasons,
        disclaimer=DISCLAIMER,
    )
