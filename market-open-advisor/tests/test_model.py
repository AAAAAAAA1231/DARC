import numpy as np

from market_advisor.model import (
    TEN_BILLION,
    classify_regime,
    fit_model,
    infinite_bootstrap_stats,
    verify_against_limit,
)
from conftest import synthetic_closes, synthetic_dates


def test_regime_rules():
    assert classify_regime(110, 105, 100, 0.04) == "上升"
    assert classify_regime(90, 95, 100, -0.04) == "下降"
    assert classify_regime(100, 100, 100, 0.0) == "震荡"


def test_ten_billion_limit_is_exact_empirical_mean():
    returns = np.array([-0.02, -0.01, 0.0, 0.01, 0.03], dtype=np.float64)
    stats = infinite_bootstrap_stats(returns)
    assert stats.n_sims == TEN_BILLION
    assert stats.source == "analytic_10b_limit"
    assert abs(stats.expected_return - float(returns.mean())) < 1e-15
    assert abs(stats.p_up - 0.4) < 1e-15


def test_streaming_mc_matches_limit():
    rng = np.random.default_rng(0)
    returns = rng.normal(0.0005, 0.01, size=180)
    limit, mc, err = verify_against_limit(returns, n_sims=400_000, seed=3)
    assert mc.n_sims == 400_000
    assert err < 0.001
    assert abs(mc.p_up - limit.p_up) < 0.02


def test_fit_model_on_uptrend():
    closes = synthetic_closes(drift=0.002, seed=11)
    model = fit_model(closes, synthetic_dates(len(closes)))
    assert model.n_hist >= 80
    assert model.n_regime >= 40
    assert model.regime in {"上升", "下降", "震荡"}
    assert model.last_close == float(closes[-1])
