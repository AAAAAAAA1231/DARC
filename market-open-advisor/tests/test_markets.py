from datetime import datetime

from market_advisor.markets import MARKET_BY_KEY, session_label, SHANGHAI


def test_session_labels_sse():
    market = MARKET_BY_KEY["sse"]
    assert session_label(market, datetime(2026, 8, 28, 8, 0, tzinfo=SHANGHAI)) == "盘前"
    assert session_label(market, datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)) == "盘中"
    assert session_label(market, datetime(2026, 8, 28, 12, 0, tzinfo=SHANGHAI)) == "午休"
    assert session_label(market, datetime(2026, 8, 28, 16, 0, tzinfo=SHANGHAI)) == "盘后"
    assert session_label(market, datetime(2026, 8, 29, 10, 0, tzinfo=SHANGHAI)) == "休市"
