from backend.strategies.indicators import candles_to_arrays
from backend.strategies.plugins import ALL_STRATEGIES


def test_all_fourteen_strategies_emit_contract():
    candles = [
        {
            "open": str(100 + i * 0.1),
            "high": str(101 + i * 0.1),
            "low": str(99 + i * 0.1),
            "close": str(100.5 + i * 0.1),
            "volume": "5",
        }
        for i in range(80)
    ]
    ohlcv = candles_to_arrays(candles)
    names = {p.name for p in ALL_STRATEGIES}
    assert len(names) == 14
    for plugin in ALL_STRATEGIES:
        sig = plugin.evaluate(ohlcv)
        payload = sig.as_dict()
        assert payload["direction"] in {"LONG", "SHORT", "NEUTRAL"}
        assert "score" in payload
        assert "confidence" in payload
        assert "signal" in payload
        assert "reason" in payload
