from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfoNotFoundError

from market_advisor.markets import MARKET_BY_KEY, load_zone, session_label, SHANGHAI


def test_session_labels_sse():
    market = MARKET_BY_KEY["sse"]
    assert session_label(market, datetime(2026, 8, 28, 8, 0, tzinfo=SHANGHAI)) == "盘前"
    assert session_label(market, datetime(2026, 8, 28, 10, 0, tzinfo=SHANGHAI)) == "盘中"
    assert session_label(market, datetime(2026, 8, 28, 12, 0, tzinfo=SHANGHAI)) == "午休"
    assert session_label(market, datetime(2026, 8, 28, 16, 0, tzinfo=SHANGHAI)) == "盘后"
    assert session_label(market, datetime(2026, 8, 29, 10, 0, tzinfo=SHANGHAI)) == "休市"


def test_load_zone_falls_back_without_tzdata(monkeypatch):
    import market_advisor.markets as markets

    def boom(_key: str):
        raise ZoneInfoNotFoundError("No time zone found with key Asia/Shanghai")

    monkeypatch.setattr(markets, "ZoneInfo", boom)
    tz = markets.load_zone("Asia/Shanghai", 8)
    assert tz.utcoffset(datetime(2026, 8, 28)) == timedelta(hours=8)
    now = datetime(2026, 8, 28, 1, 0, tzinfo=timezone.utc)
    local = now.astimezone(tz)
    assert local.hour == 9
