from datetime import datetime, timedelta, timezone

from web3_radar.engine.meme_score import enrich_and_score, select_watchlist
from web3_radar.copytrade import _exit_reason, _pnl, _should_enter


def _created(minutes_ago: float) -> int:
    return int((datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).timestamp())


def _base(**kwargs):
    row = {
        "liquidity_usd": 120000,
        "buys": 40,
        "sells": 12,
        "buys_m5": 24,
        "sells_m5": 8,
        "unique_buyers_est": 28,
        "holder_growth_est": 12,
        "holders": 120,
        "volume_h1": 40000,
        "price_change_h1": 18,
        "price_change_m5": 6,
        "price_change_h24": 40,
        "fdv": 900000,
        "price_usd": 0.002,
        "source": "gmgn+geckoterminal",
        "created_at": _created(120),
    }
    row.update(kwargs)
    return row


def test_meme_score_rejects_thin_chase_pump_and_dumping():
    thin = _base(liquidity_usd=5000)
    late = _base(price_change_h1=180)
    vertical_m5 = _base(price_change_m5=40, price_change_h1=22)
    dumping = _base(buys_m5=6, sells_m5=20, buys=10, sells=30)
    pump = _base(source="pump.fun", liquidity_usd=40000, price_change_h1=22)
    old_style_good = _base(liquidity_usd=45000, created_at=None, price_change_h1=28)

    assert enrich_and_score(thin)["grade"] == "避开"
    assert enrich_and_score(late)["grade"] == "避开"
    assert enrich_and_score(vertical_m5)["grade"] == "避开"
    assert enrich_and_score(dumping)["grade"] == "避开"
    assert enrich_and_score(pump)["grade"] == "避开"
    assert enrich_and_score(old_style_good)["followable"] is False


def test_meme_score_followable_is_alive_not_parabolic():
    good = enrich_and_score(_base())
    assert good["followable"] is True
    assert good["grade"] == "可跟"
    assert good["action"] == "小仓试错"
    assert good["heat"] >= 70
    assert good["risk"] <= 38


def test_watchlist_drops_avoid_coins():
    items = [_base(liquidity_usd=3000), _base(), _base(price_change_h1=200)]
    kept = select_watchlist(items)
    assert all(x["grade"] != "避开" for x in kept)
    assert any(x["followable"] for x in kept)


def test_copy_sl_tp_and_time_stop():
    pos = {"entry": 1.0, "qty": 30, "sl": 0.92, "tp": 1.16}
    assert _exit_reason(pos, 0.90, {}) == "止损"
    assert _exit_reason(pos, 1.17, {}) == "止盈"
    assert _exit_reason(pos, 1.05, {}) is None
    assert _pnl(pos, 1.1) == 3.0

    stale = {
        "entry": 1.0,
        "qty": 10,
        "sl": 0.92,
        "tp": 1.16,
        "opened_at": (datetime.now(timezone.utc) - timedelta(minutes=50)).isoformat(),
    }
    s = {"copy_time_stop_minutes": 45, "copy_giveup_pct": 0.03}
    assert _exit_reason(stale, 1.01, s) == "超时离场"
    assert _exit_reason(stale, 1.10, s) is None


def test_should_enter_blocks_chase():
    ok, _ = _should_enter(_base(), {"meme_min_liquidity_usd": 80000, "copy_min_heat": 70, "copy_max_risk": 38, "copy_max_1h_change": 32})
    assert ok is True
    no, why = _should_enter(_base(price_change_h1=55), {"copy_max_1h_change": 32, "copy_min_heat": 70, "copy_max_risk": 38})
    assert no is False
    assert "追" in why or "避开" in why or "评级" in why
