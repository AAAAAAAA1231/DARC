from backend.services.holdings import from_summaries, holding_signal


def test_holding_signal_bands():
    assert holding_signal(None, None) == "HOLD"
    assert holding_signal(0.5, None) == "TAKE_PROFIT"
    assert holding_signal(-0.3, None) == "EXIT"
    assert holding_signal(0.08, None) == "ADD"
    assert holding_signal(0.1, "MALICIOUS") == "HIGH_RISK"


def test_overlay_maps_base_and_pair():
    mapped = from_summaries(
        [
            {
                "id": 1,
                "status": "OPEN",
                "symbol": "BTCUSDT",
                "avg_cost": "70000",
                "quantity": "0.01",
                "net_pnl": "1.2",
                "roi": 0.08,
            }
        ]
    )
    assert mapped["BTCUSDT"]["held"] is True
    assert mapped["BTC"]["held"] is True
    assert mapped["BTC"]["signal"] == "ADD"
    closed = from_summaries([{"status": "CLOSED", "symbol": "ETHUSDT", "roi": 1.0}])
    assert closed == {}
