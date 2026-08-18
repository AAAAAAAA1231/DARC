from datetime import datetime, timedelta, timezone

from web3_radar.engine.meme_score import enrich_and_score, select_watchlist
from web3_radar.copytrade import _exit_reason, _pnl, _should_enter, apply_scale, trail_stop


def _created(minutes_ago: float) -> int:
    return int((datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).timestamp())


def _base(**kwargs):
    row = {
        "liquidity_usd": 45000,
        "buys": 40,
        "sells": 12,
        "buys_m5": 24,
        "sells_m5": 8,
        "unique_buyers_est": 22,
        "holder_growth_est": 12,
        "holders": 80,
        "volume_h1": 35000,
        "price_change_h1": 55,
        "price_change_m5": 12,
        "price_change_h24": 80,
        "fdv": 480000,
        "price_usd": 0.002,
        "source": "gmgn+pump.fun",
        "created_at": _created(90),
    }
    row.update(kwargs)
    return row


def test_meme_score_rejects_rugs_and_already_cooked():
    assert enrich_and_score(_base(liquidity_usd=5000))["grade"] == "避开"
    assert enrich_and_score(_base(price_change_h1=260))["grade"] == "避开"
    assert enrich_and_score(_base(buys_m5=4, sells_m5=20, buys=8, sells=40))["grade"] == "避开"
    assert enrich_and_score(_base(fdv=20_000_000, liquidity_usd=200000))["grade"] == "避开"


def test_meme_score_allows_small_moving_ticket():
    good = enrich_and_score(_base())
    assert good["followable"] is True
    assert good["action"] == "小仓博倍数"
    # 1h 涨 55% 对妖币是启动，不是禁止
    hot = enrich_and_score(_base(price_change_h1=55))
    assert hot["followable"] is True
    pump = enrich_and_score(_base(source="pump.fun", liquidity_usd=40000))
    assert pump["grade"] in {"可跟", "观察"}


def test_watchlist_keeps_tickets_drops_rugs():
    items = [_base(liquidity_usd=3000), _base(), _base(price_change_h1=280)]
    kept = select_watchlist(items)
    assert all(x["grade"] != "避开" for x in kept)
    assert any(x["followable"] for x in kept)


def test_copy_is_multiple_not_scalp():
    pos = {"entry": 1.0, "qty": 10, "sl": 0.70, "tp": 10.0}
    assert _exit_reason(pos, 0.65, {}) == "止损"
    assert _exit_reason(pos, 10.1, {}) == "月亮仓止盈"
    assert _exit_reason(pos, 1.50, {}) is None  # +50% 还在拿
    assert trail_stop(1.0, 0.70, 1.50) is None
    assert trail_stop(1.0, 0.70, 2.00) == 1.25
    assert trail_stop(1.0, 1.25, 5.00) == 2.5
    hit = apply_scale({"entry": 1.0, "qty": 10, "orig_qty": 10, "scale_stage": 0}, 2.1, {})
    assert hit and hit["stage"] == 1
    hit2 = apply_scale({"entry": 1.0, "qty": 7, "orig_qty": 10, "scale_stage": 1}, 5.2, {})
    assert hit2 and hit2["stage"] == 2


def test_dead_ticket_time_stop():
    stale = {
        "entry": 1.0,
        "qty": 10,
        "sl": 0.70,
        "tp": 10.0,
        "opened_at": (datetime.now(timezone.utc) - timedelta(minutes=250)).isoformat(),
    }
    s = {"copy_time_stop_minutes": 240, "copy_giveup_pct": 0.20}
    assert _exit_reason(stale, 1.05, s) == "死票离场"
    assert _exit_reason(stale, 1.50, s) is None


def test_should_enter_allows_55pct_hour():
    ok, _ = _should_enter(_base(), {"meme_min_liquidity_usd": 25000, "copy_min_heat": 60, "copy_max_risk": 62, "copy_max_1h_change": 150})
    assert ok is True
    no, why = _should_enter(_base(price_change_h1=180), {"copy_max_1h_change": 150, "copy_min_heat": 60, "copy_max_risk": 62})
    assert no is False
    assert "倍" in why or "评级" in why or "避开" in why
