from backend.backtest.engine import detect_lookahead_violation, walk_forward
from backend.strategies.plugins import ALL_STRATEGIES


def _candles(n: int = 320):
    rows = []
    price = 100.0
    for i in range(n):
        price *= 1.001 if i % 7 else 0.999
        rows.append(
            {
                "open_time": str(i),
                "open": str(price),
                "high": str(price * 1.01),
                "low": str(price * 0.99),
                "close": str(price),
                "volume": "10",
            }
        )
    return rows


def test_walk_forward_and_no_lookahead():
    weights = {p.name: p.initial_weight for p in ALL_STRATEGIES}
    wf = walk_forward(_candles(), weights, train=80, test=20)
    assert wf["ok"] is True
    assert wf["leakage_controls"]["point_in_time"] is True
    probe = detect_lookahead_violation(_candles(120), weights)
    assert probe["ok"] is True
    assert probe["signal_unchanged_after_future_shuffle"] is True
