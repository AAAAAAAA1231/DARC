from __future__ import annotations

from datetime import datetime, timezone

from web3_radar.engine.cycle import MarketSnapshot, assess_cycle, classify_phase


def _dt(*args) -> datetime:
    return datetime(*args, tzinfo=timezone.utc)


def test_early_bull_after_halving_holds_coins():
    snap = MarketSnapshot(price=11_000, ath=20_000, ath_date=_dt(2017, 12, 17), source="test")
    now = _dt(2020, 8, 1)
    regime, phase = classify_phase(snap, now)
    view = assess_cycle(snap, now)
    assert regime == "牛市"
    assert phase == "牛市早期"
    assert view.hold == "持币"
    assert view.allocations[0].symbol == "BTC"
    assert view.allocations[0].weight_pct >= 60


def test_late_bull_near_ath_holds_cash():
    snap = MarketSnapshot(price=62_000, ath=64_000, ath_date=_dt(2021, 10, 15), source="test")
    now = _dt(2021, 10, 20)
    view = assess_cycle(snap, now)
    assert view.regime == "牛市"
    assert view.phase == "牛市末期"
    assert "U" in view.hold
    assert view.allocations[0].symbol == "USDT"


def test_early_bear_after_peak_holds_usdt():
    snap = MarketSnapshot(price=42_000, ath=69_000, ath_date=_dt(2021, 11, 10), source="test")
    view = assess_cycle(snap, _dt(2022, 1, 15))
    assert view.regime == "熊市"
    assert view.phase == "熊市早期"
    assert view.hold == "持U"
    assert view.allocations[0].symbol == "USDT"
    assert view.allocations[0].weight_pct >= 70


def test_late_bear_starts_holding_btc():
    snap = MarketSnapshot(price=17_000, ath=69_000, ath_date=_dt(2021, 11, 10), source="test")
    view = assess_cycle(snap, _dt(2022, 12, 15))
    assert view.regime == "熊市"
    assert "筑底" in view.phase or "末期" in view.phase
    assert view.hold == "持币为主"
    assert view.allocations[0].symbol == "BTC"


def test_mid_bear_in_2026_if_off_cycle_highs():
    snap = MarketSnapshot(price=72_000, ath=120_000, ath_date=_dt(2025, 10, 6), source="test")
    view = assess_cycle(snap, _dt(2026, 9, 1))
    assert view.regime == "熊市"
    assert view.phase == "熊市中期"
    assert view.hold == "持U为主"
    assert view.hold_days > 0
    assert view.hold_until
    assert view.history
    assert view.typical_bull_days > 400
    assert view.typical_bear_days > 300
