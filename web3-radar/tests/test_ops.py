from datetime import datetime, timedelta, timezone

from web3_radar.collectors.social import (
    collect_social,
    looks_like_ambassador_post,
    looks_like_cex_listing,
    looks_like_project_launch,
    looks_like_solana_launch,
)
from web3_radar.copytrade import halt_new_entries, position_size_usd, recently_closed, token_id, trail_stop, _exit_reason
from web3_radar.db import analysis_is_fitted
from web3_radar.fallback import merge_items


def test_trail_stop_breakeven_then_lock():
    assert trail_stop(1.0, 0.82, 1.10) is None
    assert trail_stop(1.0, 0.82, 1.25) == 1.0
    locked = trail_stop(1.0, 1.0, 1.60)
    assert locked == 1.3


def test_exit_reason_trailing_vs_stop():
    pos = {"entry": 1.0, "qty": 30, "sl": 1.0, "tp": 1.4}
    assert _exit_reason(pos, 0.99, {}) == "止损"
    pos["sl"] = 1.2
    assert _exit_reason(pos, 1.2, {}) == "追踪止盈"


def test_position_size_capped_at_five_percent():
    assert position_size_usd({"copy_paper_equity": 1000, "copy_size_usd": 30, "copy_max_size_pct": 0.05}) == 30
    assert position_size_usd({"copy_paper_equity": 200, "copy_size_usd": 30, "copy_max_size_pct": 0.05}) == 10


def test_cooldown_and_token_id():
    now = datetime(2026, 8, 17, tzinfo=timezone.utc)
    closed = [{
        "item_key": "solana:abc",
        "token_address": "abc",
        "chain": "Solana",
        "closed_at": (now - timedelta(minutes=10)).isoformat(),
    }]
    assert recently_closed(closed, "solana:abc", 60, now=now)
    assert not recently_closed(closed, "solana:abc", 5, now=now)
    assert token_id({"chain_id": "solana", "token_address": "AbC"}) == "solana:abc"


def test_daily_loss_halt():
    now = datetime(2026, 8, 17, 12, tzinfo=timezone.utc)
    s = {"copy_paper_equity": 850, "copy_daily_loss_pct": 0.15}
    positions = [{"status": "closed", "pnl_usd": -160, "closed_at": now.isoformat()}]
    assert halt_new_entries(s, positions, now=now)


def test_fitted_allows_twenty_percent_failures():
    ok = [{"n_sims": 1_000_000} for _ in range(80)]
    bad = [{"n_sims": 0, "error": "kline"} for _ in range(20)]
    fitted, n, total = analysis_is_fitted(ok + bad)
    assert fitted is True
    assert n == 80
    assert total == 100
    fitted2, _, _ = analysis_is_fitted(ok[:50] + bad)
    assert fitted2 is False
    infer = [{"mode": "infer", "weights_adjusted": True} for _ in range(90)] + [{"error": "x"} for _ in range(10)]
    fitted3, n3, total3 = analysis_is_fitted(infer)
    assert fitted3 is True
    assert n3 == 90
    assert total3 == 100


def test_project_launch_not_cex_listing():
    assert looks_like_cex_listing("OKX to list GRVT/USDT for spot trading")
    assert looks_like_cex_listing("Binance will list ABCUSDT Launchpool")
    assert not looks_like_project_launch("OKX to list GRVT/USDT for spot trading")
    assert looks_like_project_launch("Whitelist is open for our TGE, presale live this week")
    assert looks_like_solana_launch("Solana whitelist is open for our TGE, presale live this week")
    assert not looks_like_solana_launch("Whitelist is open for our TGE, presale live this week")
    assert looks_like_ambassador_post("We're hiring regional ambassadors, apply via the form")
    assert not looks_like_ambassador_post("Join the Binance campus ambassador program", "binance")
    merged = merge_items(
        [{"key": "live-1", "name": "新项目", "source_kind": "live"}],
        [{"key": "seed-1", "name": "观察", "source": "观察池"}],
    )
    assert merged[-1]["source_kind"] == "seed"
    assert merged[-1]["fallback"] is True


def test_solana_follow_launch_timing():
    from web3_radar.collectors.solana_watch import (
        diff_new_follows,
        extract_launch_when,
        extract_mentions,
        looks_like_launch_alert,
        to_item,
    )

    posted = datetime(2026, 8, 20, 10, 0, tzinfo=timezone.utc)
    now = datetime(2026, 8, 20, 10, 5, tzinfo=timezone.utc)
    rel = extract_launch_when("TGE in 6 hours, get ready", posted, now=now)
    assert rel["status"] == "即将发射"
    assert "北京时间" in rel["when_cn"]
    today = extract_launch_when("We launch today at 8pm UTC", posted, now=now)
    assert today["source"] in {"relative", "date"}
    dated = extract_launch_when("Launching August 21 at 8pm UTC", posted, now=now)
    assert dated["when_utc"].startswith("2026-08-21T20:00")
    posted_only = extract_launch_when("our token launch is live now!!!", posted, now=now)
    assert "发现时间" in posted_only["label"] or posted_only["relation"] in {"now", "posted"}
    assert looks_like_launch_alert("发射时间今晚，TGE now live")
    assert not looks_like_launch_alert("we shipped a blog post")
    assert extract_mentions("Welcome @FooBar to Solana", ["solana"]) == ["foobar"]
    assert "solana" not in extract_mentions("gm @solana @NewThing")
    assert diff_new_follows(["alpha", "beta"], ["alpha"]) == {"beta"}
    assert diff_new_follows(["alpha"], None) == set()
    row = to_item(
        {"username": "alpha", "name": "Alpha", "description": "TGE on Solana", "public_metrics": {"followers_count": 3000}},
        True,
        {"text": "launch in 2 hours", "created_at": posted.isoformat(), "url": "https://x.com/alpha/status/1",
         "timing": extract_launch_when("launch in 2 hours", posted, now=now)},
        "following",
        rank=1,
        followed_by=["solana", "toly"],
    )
    assert row["alert"] is True
    assert row["watch_kind"] == "solana_follow"
    assert row["verified_follow"] is True
    assert "solana" in row["followed_by"] and "toly" in row["followed_by"]
    assert row["official_follow_count"] == 2
    assert row["official_follow_total"] == 3
    assert row["follow_count_label"] == "官方关注 2/3"
    assert "@solana" in row["follow_proof"] and "@toly" in row["follow_proof"]
    assert row["followers"] == 3000
    assert "北京时间" in row["launch_when_label"]
    fake = to_item(
        {"username": "pumpfun", "name": "Pump", "description": "not followed", "public_metrics": {}},
        False, None, "seed", followed_by=[],
    )
    assert fake is None
    from web3_radar.collectors.solana_watch import verified_followers
    assert verified_followers(["solana"]) == ["solana"]
    assert verified_followers(["binance", "someone"]) == []


def test_collect_social_without_bearer_does_not_crash():
    import asyncio
    rows = asyncio.run(collect_social(["ambassador"], "", 7))
    assert isinstance(rows, list)
