from backend.simulations.monte_carlo import gbm_terminal_prices, lottery_coverage_sim


def test_gbm_vectorized_quantiles():
    result = gbm_terminal_prices(100, 0.0, 0.2, 1.0, paths=50_000, seed=1, chunk=10_000)
    assert result["paths"] == 50_000
    assert result["quantiles"]["p50"] > 0
    assert "accuracy" not in result


def test_lottery_does_not_claim_win():
    hist = [{"red": ["1", "2", "3", "4", "5", "6"], "blue": ["7"]}]
    result = lottery_coverage_sim("ssq", hist, 20_000, chunk=5_000)
    assert result["ok"] is True
    assert "win probability skill" in result.get("coverage_note", "") or "uniform" in result.get("coverage_note", "")
