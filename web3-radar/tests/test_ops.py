from datetime import datetime, timedelta, timezone

from web3_radar.collectors.launch import parse_okx_listing
from web3_radar.collectors.social import collect_social
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


def test_okx_listing_parser_and_seed_badge():
    row = {
        "title": "OKX to list GRVT/USDT (Grvt) for spot trading",
        "url": "https://www.okx.com/help/x",
        "pTime": "1785380409432",
    }
    item = parse_okx_listing(row)
    assert item["extra"]["base"] == "GRVT"
    assert item["source_kind"] == "live"
    merged = merge_items([item], [{"key": "seed-1", "name": "观察", "source": "观察池"}])
    assert merged[-1]["source_kind"] == "seed"
    assert merged[-1]["fallback"] is True


def test_collect_social_skips_without_bearer():
    import asyncio
    assert asyncio.run(collect_social(["ambassador"], "", 7)) == []
