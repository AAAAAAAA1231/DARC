import numpy as np

from backend.services.football import predict_match


def test_probabilities_sum_to_one():
    rng = np.random.default_rng(0)
    stats = {
        "A": {"gf": 20, "ga": 10, "n": 10, "home_gf": 12, "home_n": 5, "away_gf": 8, "away_n": 5},
        "B": {"gf": 12, "ga": 18, "n": 10, "home_gf": 6, "home_n": 5, "away_gf": 6, "away_n": 5},
    }
    pred = predict_match("A", "B", {"A": 1600, "B": 1500}, stats, rng)
    s = pred["home_win"] + pred["draw"] + pred["away_win"]
    assert abs(s - 1) < 1e-6
    assert pred["injuries"] == "UNKNOWN"
    assert pred["xg"] == "UNKNOWN"
    assert 0 <= pred["over_25"] <= 1
