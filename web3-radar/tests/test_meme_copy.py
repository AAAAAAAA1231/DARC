from datetime import datetime, timedelta, timezone

from web3_radar.engine.meme_score import enrich_and_score, select_watchlist
from web3_radar.copytrade import _exit_reason, _should_enter, apply_scale, trail_stop


def _created(minutes_ago: float) -> int:
    return int((datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).timestamp())


def _base(**kwargs):
    row = {
        "liquidity_usd": 80000,
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
        "source": "gmgn+geckoterminal",
        "created_at": _created(90),
    }
    row.update(kwargs)
    return row


def test_meme_score_rejects_rugs_and_already_cooked():
    assert enrich_and_score(_base(liquidity_usd=5000))["grade"] == "避开"
    assert enrich_and_score(_base(price_change_h1=200))["grade"] == "避开"
    assert enrich_and_score(_base(buys_m5=4, sells_m5=20, buys=8, sells=40))["grade"] == "避开"
    assert enrich_and_score(_base(price_change_m5=55, price_change_h1=55))["grade"] == "避开"


def test_meme_score_follow_is_dip_in_trend():
    good = enrich_and_score(_base())
    assert good["followable"] is True
    assert good["action"] == "回踩小仓"
    spike = enrich_and_score(_base(price_change_m5=36, price_change_h1=55))
    assert spike["followable"] is False


def test_watchlist_keeps_tickets_drops_rugs():
    items = [_base(liquidity_usd=3000), _base(), _base(price_change_h1=200)]
    kept = select_watchlist(items)
    assert all(x["grade"] != "避开" for x in kept)
    assert any(x["followable"] for x in kept)


def test_copy_locks_win_then_lets_runner_go():
    pos = {"entry": 1.0, "qty": 10, "sl": 0.80, "tp": 10.0}
    assert _exit_reason(pos, 0.75, {}) == "止损"
    assert _exit_reason(pos, 1.40, {}) is None
    assert trail_stop(1.0, 0.80, 1.50) is None
    assert trail_stop(1.0, 0.80, 1.60) == 1.0
    assert trail_stop(1.0, 1.0, 3.00) == 1.6
    hit = apply_scale({"entry": 1.0, "qty": 10, "orig_qty": 10, "scale_stage": 0}, 1.65, {})
    assert hit and hit["stage"] == 1
    hit2 = apply_scale({"entry": 1.0, "qty": 5.5, "orig_qty": 10, "scale_stage": 1}, 3.2, {})
    assert hit2 and hit2["stage"] == 2


def test_fast_fail_and_dead_ticket():
    now = datetime.now(timezone.utc)
    baby = {
        "entry": 1.0,
        "qty": 10,
        "sl": 0.80,
        "tp": 10.0,
        "opened_at": (now - timedelta(minutes=12)).isoformat(),
    }
    s = {"copy_fast_fail_minutes": 20, "copy_fast_fail_pct": 0.10, "copy_time_stop_minutes": 90, "copy_giveup_pct": 0.15}
    assert _exit_reason(baby, 0.88, s, now=now) == "快速止损"
    stale = dict(baby, opened_at=(now - timedelta(minutes=100)).isoformat())
    assert _exit_reason(stale, 1.05, s, now=now) == "死票离场"
    assert _exit_reason(stale, 1.40, s, now=now) is None


def test_should_enter_wants_started_but_not_vertical():
    ok, _ = _should_enter(_base(), {"meme_min_liquidity_usd": 40000, "copy_min_heat": 64, "copy_max_risk": 55, "copy_max_1h_change": 110})
    assert ok is True
    no, why = _should_enter(_base(price_change_m5=40), {"copy_max_1h_change": 110, "copy_min_heat": 64, "copy_max_risk": 55, "meme_max_m5_change": 28})
    assert no is False
    assert "陡" in why or "评级" in why or "避开" in why or "飞刀" in why
