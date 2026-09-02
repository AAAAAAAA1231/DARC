from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

USER_AGENT = "GongZuoTai/1.1 (4y cycle board; not investment advice)"

HALVINGS = (
    datetime(2012, 11, 28, tzinfo=timezone.utc),
    datetime(2016, 7, 9, tzinfo=timezone.utc),
    datetime(2020, 5, 11, tzinfo=timezone.utc),
    datetime(2024, 4, 20, tzinfo=timezone.utc),
)

# Next halving is ~4 years after the previous; used only as a calendar marker.
NEXT_HALVING_EST = datetime(2028, 4, 20, tzinfo=timezone.utc)

KNOWN_PEAKS = (
    datetime(2013, 11, 30, tzinfo=timezone.utc),
    datetime(2017, 12, 17, tzinfo=timezone.utc),
    datetime(2021, 11, 10, tzinfo=timezone.utc),
)

KNOWN_BOTTOMS = (
    datetime(2015, 1, 14, tzinfo=timezone.utc),
    datetime(2018, 12, 15, tzinfo=timezone.utc),
    datetime(2022, 11, 21, tzinfo=timezone.utc),
)


@dataclass(frozen=True)
class MarketSnapshot:
    price: float
    ath: float
    ath_date: datetime
    change_30d: Optional[float] = None
    change_365d: Optional[float] = None
    source: str = "manual"


@dataclass
class Allocation:
    symbol: str
    name: str
    weight_pct: int
    hold_days: int
    hold_until: str
    reason: str


@dataclass
class CycleHistoryRow:
    label: str
    halving: str
    peak: str
    bottom: str
    bull_days: Optional[int]
    bear_days: Optional[int]


@dataclass
class CycleView:
    as_of: str
    regime: str
    phase: str
    hold: str
    hold_detail: str
    narrative: str
    price: float
    ath: float
    ath_date: str
    drawdown_pct: float
    days_since_halving: int
    days_since_ath: int
    days_to_next_halving: int
    cycle_index: int
    next_event: str
    typical_bull_days: int
    typical_bear_days: int
    allocations: list[Allocation] = field(default_factory=list)
    history: list[CycleHistoryRow] = field(default_factory=list)
    source: str = ""
    disclaimer: str = "按历史减半周期和当前回撤做的阶段判断，不是投资建议。"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload


def _iso_day(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def last_halving(now: datetime) -> datetime:
    past = [h for h in HALVINGS if h <= now]
    return past[-1] if past else HALVINGS[0]


def next_halving(now: datetime) -> datetime:
    future = [h for h in HALVINGS if h > now]
    return future[0] if future else NEXT_HALVING_EST


def median_int(values: list[int]) -> int:
    ordered = sorted(values)
    if not ordered:
        return 0
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return int(round((ordered[mid - 1] + ordered[mid]) / 2))


def historical_lengths() -> tuple[int, int, list[CycleHistoryRow]]:
    rows: list[CycleHistoryRow] = []
    bull_days: list[int] = []
    bear_days: list[int] = []
    bottoms_for_start = (
        datetime(2011, 11, 18, tzinfo=timezone.utc),
        *KNOWN_BOTTOMS,
    )
    for i, peak in enumerate(KNOWN_PEAKS):
        start = bottoms_for_start[i]
        bottom = KNOWN_BOTTOMS[i]
        bull = (peak - start).days
        bear = (bottom - peak).days
        bull_days.append(bull)
        bear_days.append(bear)
        rows.append(
            CycleHistoryRow(
                label=f"第 {i + 1} 轮",
                halving=_iso_day(HALVINGS[i]),
                peak=_iso_day(peak),
                bottom=_iso_day(bottom),
                bull_days=bull,
                bear_days=bear,
            )
        )
    rows.append(
        CycleHistoryRow(
            label="第 4 轮（进行中）",
            halving=_iso_day(HALVINGS[3]),
            peak="待本轮确认",
            bottom="未走完",
            bull_days=None,
            bear_days=None,
        )
    )
    return median_int(bull_days), median_int(bear_days), rows


def classify_phase(snapshot: MarketSnapshot, now: datetime) -> tuple[str, str]:
    """Return (regime, phase). Regime is 牛市 or 熊市."""
    drawdown = 0.0 if snapshot.ath <= 0 else max(0.0, 1.0 - snapshot.price / snapshot.ath)
    halving = last_halving(now)
    days_h = max((now - halving).days, 0)
    days_ath = max((now - snapshot.ath_date).days, 0)
    ath_this_cycle = snapshot.ath_date >= halving

    if ath_this_cycle and drawdown < 0.12:
        if days_h < 280:
            return "牛市", "牛市中期"
        return "牛市", "牛市末期"
    if ath_this_cycle and drawdown < 0.22 and days_ath <= 75:
        return "牛市", "牛市末期"
    if ath_this_cycle and drawdown >= 0.20:
        if days_ath < 120:
            return "熊市", "熊市早期"
        if drawdown < 0.55:
            return "熊市", "熊市中期"
        return "熊市", "熊市末期 / 筑底"
    if not ath_this_cycle:
        if days_h < 180:
            return "牛市", "牛市早期"
        if days_h < 400:
            return "牛市", "牛市中期"
        if days_h < 560:
            return "牛市", "牛市末期"
        if drawdown >= 0.45:
            return "熊市", "熊市中期"
        return "熊市", "熊市早期"

    if days_h < 200:
        return "牛市", "牛市早期"
    if days_h < 450:
        return "牛市", "牛市中期"
    if days_h < 600:
        return "牛市", "牛市末期"
    if days_h < 900:
        return "熊市", "熊市早期"
    if days_h < 1100:
        return "熊市", "熊市中期"
    return "熊市", "熊市末期 / 筑底"


def _until(now: datetime, days: int) -> str:
    return _iso_day(now + timedelta(days=days))


def allocations_for(phase: str, now: datetime, typical_bull: int, typical_bear: int) -> tuple[str, str, list[Allocation]]:
    if phase == "牛市早期":
        days = max(typical_bull - 90, 240)
        return (
            "持币",
            "周期刚从底部起来，先拿最硬的币，现金只留机动。",
            [
                Allocation("BTC", "比特币", 70, days, _until(now, days), "减半后主升浪通常先由 BTC 带节奏"),
                Allocation("ETH", "以太坊", 20, max(days - 30, 180), _until(now, max(days - 30, 180)), "大市值里弹性第二位"),
                Allocation("USDT", "美元稳定币", 10, 90, _until(now, 90), "只留补仓和手续费"),
            ],
        )
    if phase == "牛市中期":
        days = max(typical_bull // 2, 150)
        return (
            "持币",
            "主升段还在，可以拿 BTC + 少数大市值，不在这个阶段换一堆山寨。",
            [
                Allocation("BTC", "比特币", 50, days, _until(now, days), "仍是周期核心仓"),
                Allocation("ETH", "以太坊", 25, days, _until(now, days), "中期开始补弹性"),
                Allocation("SOL", "Solana", 15, max(days - 40, 90), _until(now, max(days - 40, 90)), "大市值里波动更大的一只，仓位要小于 BTC"),
                Allocation("USDT", "美元稳定币", 10, 60, _until(now, 60), "留给减仓，不是去加杠杆"),
            ],
        )
    if phase == "牛市末期":
        days_cash = max(typical_bear // 2, 150)
        days_btc = 90
        return (
            "持U为主",
            "历史顶部多出现在减半后 12–18 个月。这个阶段先保住筹码，而不是追最后一浪。",
            [
                Allocation("USDT", "美元稳定币", 60, days_cash, _until(now, days_cash), "先把利润落到稳定币，等熊市中后段再接"),
                Allocation("BTC", "比特币", 30, days_btc, _until(now, days_btc), "留底仓，但不再加山寨"),
                Allocation("ETH", "以太坊", 10, 60, _until(now, 60), "只留小仓，准备先减"),
            ],
        )
    if phase == "熊市早期":
        days = max(typical_bear - 60, 180)
        return (
            "持U",
            "顶部确认后的第一段下跌最快。现金为主，不要急着抄第一个坑。",
            [
                Allocation("USDT", "美元稳定币", 80, days, _until(now, days), "等波动收窄、时间换空间"),
                Allocation("BTC", "比特币", 20, days + 180, _until(now, days + 180), "只留观察仓，按周定额，不一次打满"),
            ],
        )
    if phase == "熊市中期":
        days_cash = max(typical_bear // 2, 120)
        days_btc = max(typical_bear + 180, 360)
        return (
            "持U为主",
            "中段熊市仍然磨人，但可以用时间换下一轮。现金仍是主仓，BTC 开始定投。",
            [
                Allocation("USDT", "美元稳定币", 65, days_cash, _until(now, days_cash), "还没到全面转持币"),
                Allocation("BTC", "比特币", 35, days_btc, _until(now, days_btc), "定投接到下一轮减半附近"),
            ],
        )
    # 熊市末期 / 筑底
    days = max(typical_bull, 400)
    return (
        "持币为主",
        "历史底部附近开始把现金换成最硬的币，拿过下一轮主升，而不是等新闻确认。",
        [
            Allocation("BTC", "比特币", 70, days, _until(now, days), "下一轮周期的底仓"),
            Allocation("ETH", "以太坊", 20, days, _until(now, days), "筑底后弹性通常好于一篮子山寨"),
            Allocation("USDT", "美元稳定币", 10, 120, _until(now, 120), "只留补仓"),
        ],
    )


def assess_cycle(snapshot: MarketSnapshot, now: Optional[datetime] = None) -> CycleView:
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    typical_bull, typical_bear, history = historical_lengths()
    regime, phase = classify_phase(snapshot, now)
    hold, hold_detail, allocs = allocations_for(phase, now, typical_bull, typical_bear)
    drawdown = 0.0 if snapshot.ath <= 0 else max(0.0, 1.0 - snapshot.price / snapshot.ath)
    halving = last_halving(now)
    nxt = next_halving(now)
    days_h = max((now - halving).days, 0)
    days_ath = max((now - snapshot.ath_date).days, 0)
    days_next = max((nxt - now).days, 0)
    cycle_index = 1 + sum(1 for h in HALVINGS if h <= now)

    if regime == "牛市":
        next_event = (
            f"按历史中位，牛市段大约 {typical_bull} 天；从本次减半起已过 {days_h} 天。"
            if phase != "牛市末期"
            else f"已接近历史顶部窗口。若见顶，熊市中位约 {typical_bear} 天。"
        )
    else:
        next_event = (
            f"历史熊市中位约 {typical_bear} 天。距上次减半 {days_h} 天，距下次减半约 {days_next} 天。"
        )

    narrative = (
        f"当前按四年减半周期判断为「{phase}」。"
        f"BTC 现价约 ${snapshot.price:,.0f}，距历史高点 {drawdown * 100:.1f}% "
        f"（ATH ${snapshot.ath:,.0f}，{_iso_day(snapshot.ath_date)}）。"
        f"建议先{hold}：{hold_detail}"
    )

    return CycleView(
        as_of=now.astimezone(timezone.utc).isoformat(),
        regime=regime,
        phase=phase,
        hold=hold,
        hold_detail=hold_detail,
        narrative=narrative,
        price=round(snapshot.price, 2),
        ath=round(snapshot.ath, 2),
        ath_date=_iso_day(snapshot.ath_date),
        drawdown_pct=round(drawdown * 100, 2),
        days_since_halving=days_h,
        days_since_ath=days_ath,
        days_to_next_halving=days_next,
        cycle_index=cycle_index,
        next_event=next_event,
        typical_bull_days=typical_bull,
        typical_bear_days=typical_bear,
        allocations=allocs,
        history=history,
        source=snapshot.source,
    )


def _get_json(url: str, timeout: int = 18) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError, OSError):
        return None


def fetch_btc_snapshot() -> MarketSnapshot:
    gecko = _get_json(
        "https://api.coingecko.com/api/v3/coins/bitcoin"
        "?localization=false&tickers=false&community_data=false&developer_data=false&sparkline=false"
    )
    if isinstance(gecko, dict):
        md = gecko.get("market_data") or {}
        price = float((md.get("current_price") or {}).get("usd") or 0)
        ath = float((md.get("ath") or {}).get("usd") or 0)
        ath_date = _parse_dt((md.get("ath_date") or {}).get("usd"))
        if price > 0 and ath > 0 and ath_date:
            return MarketSnapshot(
                price=price,
                ath=ath,
                ath_date=ath_date,
                change_30d=_as_float(md.get("price_change_percentage_30d")),
                change_365d=_as_float(md.get("price_change_percentage_1y")),
                source="coingecko",
            )

    ticker = _get_json("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT")
    klines = _get_json("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1000")
    price = float((ticker or {}).get("price") or 0) if isinstance(ticker, dict) else 0.0
    ath = price
    ath_date = datetime.now(timezone.utc)
    if isinstance(klines, list) and klines:
        best = 0.0
        best_ts = None
        for row in klines:
            try:
                high = float(row[2])
                ts = int(row[0])
            except (TypeError, ValueError, IndexError):
                continue
            if high >= best:
                best = high
                best_ts = ts
        if best > 0:
            ath = max(best, price)
            if best_ts:
                ath_date = datetime.fromtimestamp(best_ts / 1000.0, tz=timezone.utc)
    if price <= 0:
        raise RuntimeError("无法获取 BTC 价格，四年周期板暂不可用")
    if ath <= 0:
        ath = price
    return MarketSnapshot(price=price, ath=ath, ath_date=ath_date, source="binance")


def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def current_cycle(now: Optional[datetime] = None) -> CycleView:
    return assess_cycle(fetch_btc_snapshot(), now=now)
