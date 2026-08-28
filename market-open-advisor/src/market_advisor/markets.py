"""Trading venues and the public index each venue is represented by.

Quotes are exchange prints from public feeds (Yahoo / Tencent / Sina /
East Money). Tonghuashun shows the same prints; this is not a Tonghuashun
client scrape.
"""

from __future__ import annotations

from datetime import timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dataclasses import dataclass

try:
    import tzdata as _tzdata  # noqa: F401  — needed on Windows / PyInstaller
except ImportError:
    _tzdata = None


def load_zone(key: str, utc_offset_hours: int) -> tzinfo:
    """IANA zone if tzdata is present; otherwise a fixed UTC offset.

    Frozen Windows builds often ship without the tz database. A-share/HK
    sessions are UTC+8 year-round, so the offset fallback stays correct.
    """
    try:
        return ZoneInfo(key)
    except (ZoneInfoNotFoundError, KeyError, OSError):
        return timezone(timedelta(hours=utc_offset_hours))


SHANGHAI = load_zone("Asia/Shanghai", 8)
NEW_YORK = load_zone("America/New_York", -4)


@dataclass(frozen=True)
class Market:
    key: str
    name: str
    exchange: str
    secid: str
    yahoo: str | None
    sina: str | None
    tencent: str | None
    timezone: tzinfo
    open_hour: int
    open_minute: int
    close_hour: int
    close_minute: int
    lunch_break: bool = False


MARKETS: tuple[Market, ...] = (
    Market(
        key="sse",
        name="上交所主板",
        exchange="SSE",
        secid="1.000001",
        yahoo="000001.SS",
        sina="sh000001",
        tencent="sh000001",
        timezone=SHANGHAI,
        open_hour=9,
        open_minute=30,
        close_hour=15,
        close_minute=0,
        lunch_break=True,
    ),
    Market(
        key="szse",
        name="深交所主板",
        exchange="SZSE",
        secid="0.399001",
        yahoo="399001.SZ",
        sina="sz399001",
        tencent="sz399001",
        timezone=SHANGHAI,
        open_hour=9,
        open_minute=30,
        close_hour=15,
        close_minute=0,
        lunch_break=True,
    ),
    Market(
        key="chinext",
        name="创业板",
        exchange="SZSE ChiNext",
        secid="0.399006",
        yahoo="399006.SZ",
        sina="sz399006",
        tencent="sz399006",
        timezone=SHANGHAI,
        open_hour=9,
        open_minute=30,
        close_hour=15,
        close_minute=0,
        lunch_break=True,
    ),
    Market(
        key="star",
        name="科创板",
        exchange="SSE STAR",
        secid="1.000688",
        yahoo="000688.SS",
        sina="sh000688",
        tencent="sh000688",
        timezone=SHANGHAI,
        open_hour=9,
        open_minute=30,
        close_hour=15,
        close_minute=0,
        lunch_break=True,
    ),
    Market(
        key="bse",
        name="北交所",
        exchange="BSE",
        secid="0.899050",
        yahoo=None,
        sina="bj899050",
        tencent="bj899050",
        timezone=SHANGHAI,
        open_hour=9,
        open_minute=30,
        close_hour=15,
        close_minute=0,
        lunch_break=True,
    ),
    Market(
        key="hkex",
        name="港交所",
        exchange="HKEX",
        secid="100.HSI",
        yahoo="^HSI",
        sina=None,
        tencent="hkHSI",
        timezone=SHANGHAI,
        open_hour=9,
        open_minute=30,
        close_hour=16,
        close_minute=0,
        lunch_break=True,
    ),
    Market(
        key="us",
        name="美股",
        exchange="NYSE/Nasdaq",
        secid="100.NDX",
        yahoo="^NDX",
        sina=None,
        tencent="usNDX",
        timezone=NEW_YORK,
        open_hour=9,
        open_minute=30,
        close_hour=16,
        close_minute=0,
        lunch_break=False,
    ),
)

MARKET_BY_KEY = {m.key: m for m in MARKETS}


def session_label(market: Market, now) -> str:
    local = now.astimezone(market.timezone)
    minutes = local.hour * 60 + local.minute
    open_m = market.open_hour * 60 + market.open_minute
    close_m = market.close_hour * 60 + market.close_minute
    if local.weekday() >= 5:
        return "休市"
    if minutes < open_m:
        return "盘前"
    if minutes >= close_m:
        return "盘后"
    if market.lunch_break and 11 * 60 + 30 <= minutes < 13 * 60:
        return "午休"
    return "盘中"
