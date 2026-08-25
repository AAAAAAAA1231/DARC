import numpy as np

from a_share_trading.methods import METHODS
from a_share_trading.simulator import run_monte_carlo


def test_monte_carlo_prefers_higher_mu_method():
    n = len(METHODS)
    mu = np.zeros(n)
    mu[0] = 0.02
    mu[1] = -0.01
    cov = np.eye(n) * 0.01
    result = run_monte_carlo(mu, cov, n_sims=200_000, batch=50_000, workers=1, seed=7)
    assert result["n_sims"] == 200_000
    assert result["posterior_weights"][0] > result["posterior_weights"][1]
    assert result["best_weights"][0] > result["best_weights"][1]
    assert result["best_sharpe"] > 0
