from datetime import datetime, timedelta, timezone

from web3_radar.engine.meme_score import enrich_and_score, period_pick, select_watchlist
from web3_radar.copytrade import _exit_reason, _should_enter, apply_scale, trail_stop


def _created(minutes_ago: float) -> int:
    return int((datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).timestamp())


def _base(**kwargs):
    row = {
        "symbol": "HBULL",
        "name": "Hyper Bull",
        "liquidity_usd": 130000,
        "buys": 40,
        "sells": 18,
        "buys_m5": 12,
        "sells_m5": 7,
        "unique_buyers_est": 40,
        "holder_growth_est": 12,
        "holders": 120,
        "volume_h24": 900000,
        "volume_h1": 80000,
        "price_change_h1": 4,
        "price_change_h6": 8,
        "price_change_m5": 3,
        "price_change_h24": 28,
        "fdv": 900000,
        "price_usd": 0.0009,
        "source": "dexscreener+geckoterminal",
        "has_twitter": True,
        "twitter": "https://x.com/hyperbullsol",
        "created_at": _created(60 * 24 * 12),
    }
    row.update(kwargs)
    return row


def test_meme_score_rejects_rugs_and_already_cooked():
    assert enrich_and_score(_base(liquidity_usd=5000))["grade"] == "避开"
    assert enrich_and_score(_base(created_at=_created(20)))["grade"] == "避开"
    assert enrich_and_score(_base(price_change_h24=400))["grade"] == "避开"
    assert enrich_and_score(_base(price_change_h24=-50))["grade"] == "避开"
    assert enrich_and_score(_base(buys_m5=4, sells_m5=20, buys=8, sells=40))["grade"] == "避开"


def test_meme_score_follow_is_10day_survivor():
    good = enrich_and_score(_base())
    assert good["followable"] is True
    assert good["action"] == "10天小仓"
    assert good["conviction"] is True
    baby = enrich_and_score(_base(created_at=_created(12 * 60), price_change_h24=900))
    assert baby["followable"] is False
    no_social = enrich_and_score(_base(has_twitter=False, twitter="", source="dexscreener", gecko_trending=False, is_cto=False))
    assert no_social["followable"] is False
    vertical = enrich_and_score(_base(price_change_h1=40))
    assert vertical["followable"] is False


def test_watchlist_keeps_tickets_drops_rugs():
    items = [_base(liquidity_usd=3000), _base(), _base(price_change_h24=400)]
    kept = select_watchlist(items)
    assert all(x["grade"] != "避开" for x in kept)
    assert any(x["followable"] for x in kept)
    assert period_pick(kept)["symbol"] == "HBULL"


def test_copy_locks_win_then_lets_runner_go():
    pos = {"entry": 1.0, "qty": 10, "sl": 0.75, "tp": 10.0}
    assert _exit_reason(pos, 0.70, {}) == "止损"
    assert _exit_reason(pos, 1.40, {}) is None
    assert trail_stop(1.0, 0.75, 1.50) is None
    assert trail_stop(1.0, 0.75, 2.00) == 1.0
    assert trail_stop(1.0, 1.0, 4.00) == 2.0
    hit = apply_scale({"entry": 1.0, "qty": 10, "orig_qty": 10, "scale_stage": 0}, 2.05, {})
    assert hit and hit["stage"] == 1
    assert hit["sell_qty"] == 4.0
    hit2 = apply_scale({"entry": 1.0, "qty": 6.0, "orig_qty": 10, "scale_stage": 1}, 4.10, {})
    assert hit2 and hit2["stage"] == 2


def test_fast_fail_and_dead_ticket():
    now = datetime.now(timezone.utc)
    baby = {
        "entry": 1.0,
        "qty": 10,
        "sl": 0.75,
        "tp": 10.0,
        "opened_at": (now - timedelta(minutes=120)).isoformat(),
    }
    s = {"copy_fast_fail_minutes": 360, "copy_fast_fail_pct": 0.18, "copy_time_stop_minutes": 60 * 24 * 10, "copy_giveup_pct": 0.40}
    assert _exit_reason(baby, 0.80, s, now=now) == "快速止损"
    stale = dict(baby, opened_at=(now - timedelta(days=11)).isoformat())
    assert _exit_reason(stale, 1.10, s, now=now) == "死票离场"
    assert _exit_reason(stale, 1.50, s, now=now) is None


def test_structure_break_exits_before_first_scale():
    pos = {"entry": 1.0, "qty": 10, "sl": 0.75, "tp": 10.0, "scale_stage": 0}
    tape = {"price_change_h6": -32, "price_change_m5": -4, "buys_m5": 8, "sells_m5": 9}
    assert _exit_reason(pos, 0.97, {}, tape=tape) == "结构破坏"
    locked = dict(pos, scale_stage=1)
    assert _exit_reason(locked, 0.97, {}, tape=tape) is None


def test_should_enter_wants_survivor_not_vertical():
    ok, _ = _should_enter(_base(), {})
    assert ok is True
    no, why = _should_enter(_base(created_at=_created(30)), {})
    assert no is False
    assert "评级" in why or "避开" in why
    cooked, cooked_why = _should_enter(_base(price_change_h24=200), {})
    assert cooked is False
    assert "评级" in cooked_why or "飞刀" in cooked_why or "避开" in cooked_why
