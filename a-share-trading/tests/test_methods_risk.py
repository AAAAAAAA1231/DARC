import numpy as np

from a_share_trading.data_source import Stock, synthesize_bars
from a_share_trading.ensemble import aligned_method_returns, apply_correction, combine_signals, prior_weights
from a_share_trading.methods import METHODS, all_score_matrix, last_signals
from a_share_trading.risk import build_risk_plan


def _stock():
    return Stock(
        code="600519",
        name="贵州茅台",
        symbol="sh600519",
        last=1600.0,
        open=1590.0,
        high=1610.0,
        low=1580.0,
        prev_close=1595.0,
        change_pct=0.31,
        volume=1e6,
        amount=1e9,
        pe=20.0,
        pb=8.0,
        mktcap=2e12,
        float_mktcap=2e12,
        turnover=0.2,
        exchange="SSE",
        board="主板",
        limit_pct=0.10,
        lot_size=100,
    )


def test_synthetic_bars_end_at_last():
    bars = synthesize_bars(_stock(), n=120)
    assert len(bars) == 120
    assert abs(bars.close[-1] - 1600) < 1e-6
    assert np.all(bars.high + 1e-9 >= np.maximum(bars.open, bars.close))


def test_method_scores_bounded():
    bars = synthesize_bars(_stock(), n=180)
    names, matrix = all_score_matrix(bars)
    assert names == [m.name for m in METHODS]
    assert matrix.shape[1] == len(METHODS)
    assert np.nanmax(np.abs(matrix)) <= 1.0001


def test_ensemble_weights_and_risk_sides():
    bars = synthesize_bars(_stock(), n=180)
    signals = last_signals(bars)
    weights = prior_weights()
    assert abs(weights.sum() - 1) < 1e-9
    ens = combine_signals(signals, weights)
    plan = build_risk_plan(_stock(), bars, ens)
    assert plan.entry > 0
    assert plan.take_profit > 0 and plan.stop_loss > 0
    if ens.direction == "上涨":
        assert plan.take_profit >= plan.entry
        assert plan.stop_loss <= plan.entry
    elif ens.direction == "下跌":
        assert plan.take_profit <= plan.entry
        assert plan.stop_loss >= plan.entry


def test_aligned_method_returns_shapes():
    bars = synthesize_bars(_stock(), n=180)
    mu, cov = aligned_method_returns([bars], horizon=5, cost=0.0008)
    n = len(METHODS)
    assert mu.shape == (n,)
    assert cov.shape == (n, n)
    assert np.isfinite(mu).all()
    assert np.isfinite(cov).all()


def test_correction_normalizes():
    n = len(METHODS)
    prior = np.full(n, 1 / n)
    posterior = np.linspace(1, 2, n)
    posterior = posterior / posterior.sum()
    ic = np.linspace(-0.05, 0.08, n)
    out = apply_correction(prior, posterior, ic)
    assert abs(out.sum() - 1) < 1e-9
    assert (out > 0).all()
