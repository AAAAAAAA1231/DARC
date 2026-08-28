from datetime import datetime

import numpy as np

from market_advisor.advice import ACTION_FLAT, ACTION_LONG, ACTION_SHORT, build_advice, decide_action
from market_advisor.markets import MARKETS
from market_advisor.model import FittedModel, SimulationStats


def _model(**kwargs) -> FittedModel:
    base = dict(
        returns=np.array([0.01, 0.02, -0.005]),
        regime="上升",
        last_close=3000.0,
        last_date="2026-08-27",
        ma20=2980.0,
        ma60=2900.0,
        momentum_20=0.04,
        vol_20=0.01,
        n_hist=250,
        n_regime=120,
    )
    base.update(kwargs)
    return FittedModel(**base)


def _stats(**kwargs) -> SimulationStats:
    base = dict(
        expected_return=0.004,
        p_up=0.60,
        p05=-0.01,
        p50=0.003,
        p95=0.02,
        sigma=0.01,
        n_sims=10_000_000_000,
        source="analytic_10b_limit",
    )
    base.update(kwargs)
    return SimulationStats(**base)


def test_long_short_flat_rules():
    action, size, reasons = decide_action(_stats(), _model())
    assert action == ACTION_LONG
    assert size > 0
    assert any("100亿" in row for row in reasons)

    action, size, _ = decide_action(
        _stats(expected_return=-0.004, p_up=0.40, p05=-0.03),
        _model(regime="下降", momentum_20=-0.05),
    )
    assert action == ACTION_SHORT

    action, size, _ = decide_action(_stats(expected_return=0.0, p_up=0.50, p05=-0.02), _model())
    assert action == ACTION_FLAT
    assert size == 0


def test_high_vol_cuts_size():
    _, size_lo, _ = decide_action(_stats(), _model(vol_20=0.01))
    _, size_hi, reasons = decide_action(_stats(), _model(vol_20=0.04))
    assert size_hi < size_lo
    assert any("波动" in row for row in reasons)


def test_build_advice_carries_open_time_and_disclaimer():
    opened = datetime(2026, 8, 28, 9, 31)
    item = build_advice(
        MARKETS[0],
        "上证指数",
        _model(),
        _stats(),
        _stats(n_sims=2_000_000, source="streaming_mc"),
        1e-5,
        opened,
        3001.0,
        0.15,
        "yahoo",
    )
    assert item.action == ACTION_LONG
    assert item.n_limit_sims == 10_000_000_000
    assert "投资建议" in item.disclaimer
    assert item.opened_at.startswith("2026-08-28")
