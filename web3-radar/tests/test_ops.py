from datetime import datetime, timedelta, timezone

from web3_radar.collectors.social import (
    collect_social,
    looks_like_ambassador_post,
    looks_like_cex_listing,
    looks_like_project_ambassador,
    looks_like_project_launch,
    looks_like_solana_launch,
)
from web3_radar.copytrade import (
    cooldown_minutes_for,
    consecutive_closed_losses,
    halt_new_entries,
    max_new_entries,
    position_size_usd,
    recently_closed,
    size_after_losses,
    token_id,
    trail_stop,
    _exit_reason,
)
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


def test_copy_refresh_caps_and_losing_streak():
    now = datetime(2026, 8, 21, 12, tzinfo=timezone.utc)
    losses = [
        {"status": "closed", "pnl_usd": -12, "closed_at": (now - timedelta(hours=i)).isoformat(), "close_reason": "止损", "item_key": "solana:abc", "token_address": "abc", "chain": "Solana"}
        for i in range(3)
    ]
    assert consecutive_closed_losses(losses, 3)
    n, why = max_new_entries({"copy_max_new_per_refresh": 1}, losses)
    assert n == 0
    assert "连亏" in (why or "")
    assert max_new_entries({"copy_max_new_per_refresh": 1}, []) == (1, None)
    assert size_after_losses(30, losses) == 15
    assert cooldown_minutes_for(losses, "solana:abc", "solana:abc", 60) == 120


def test_fitted_allows_twenty_percent_failures():
    ok = [{"n_sims": 1_000_000_000} for _ in range(80)]
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
    assert looks_like_project_ambassador("We're hiring regional ambassadors, apply via the form")
    assert looks_like_project_ambassador("新项目招募大使，报名走表单")
    assert not looks_like_project_ambassador("I want to be an ambassador, hire me DM")
    assert not looks_like_project_ambassador("求大使工作，想当社区大使")
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
    assert row["official_follow_total"] == 2
    assert row["follow_count_label"] == "官方关注 2/2"
    assert "@solana" in row["follow_proof"] and "@toly" in row["follow_proof"]
    assert row["followers"] == 3000
    assert row["token_status"] == "未发币"
    assert "北京时间" in row["launch_when_label"]
    fake = to_item(
        {"username": "pumpfun", "name": "Pump", "description": "not followed", "public_metrics": {}},
        False, None, "seed", followed_by=[],
    )
    assert fake is None
    from web3_radar.collectors.solana_watch import (
        FOLLOW_LOOKBACK_DAYS,
        FOLLOW_WINDOW,
        keep_unissued_project,
        verified_followers,
    )
    assert FOLLOW_LOOKBACK_DAYS == 30
    assert FOLLOW_WINDOW == 400
    assert verified_followers(["solana"]) == ["solana"]
    assert verified_followers(["binance", "someone"]) == []
    assert verified_followers(["0xmert_", "heyibinance", "cz_binance"]) == []
    assert keep_unissued_project({
        "username": "helixsvm", "name": "Helix SVM", "description": "SVM runtime for Solana apps",
        "public_metrics": {"followers_count": 1200},
    })[0]
    assert keep_unissued_project({
        "username": "helixsvm", "name": "helixsvm", "description": "",
        "public_metrics": {},
    })[0]
    assert not keep_unissued_project({
        "username": "mert", "name": "mert", "description": "",
        "public_metrics": {"followers_count": 40000},
    })[0]
    assert not keep_unissued_project({
        "username": "jack", "name": "jack", "description": "",
        "public_metrics": {},
    })[0]
    assert not keep_unissued_project({
        "username": "0xmert_", "name": "Mert Mumtaz", "description": "building DeFi on Solana",
        "public_metrics": {"followers_count": 90000},
    })[0]
    assert not keep_unissued_project({
        "username": "austin_federa", "name": "Austin Federa", "description": "Head of strategy. He is a founder.",
        "public_metrics": {"followers_count": 80000},
    })[0]
    assert not keep_unissued_project({
        "username": "jupiter_exchange", "name": "Jupiter", "description": "Solana DEX aggregator",
        "public_metrics": {"followers_count": 500000},
    })[0]
    assert to_item(
        {"username": "nimbusfi", "name": "Nimbus", "description": "BNB DeFi protocol", "public_metrics": {"followers_count": 2000}},
        True, None, "following", rank=2, followed_by=["cz_binance"],
    ) is None
    only_sol = to_item(
        {"username": "nimbusfi", "name": "Nimbus", "description": "Solana DeFi protocol", "public_metrics": {"followers_count": 2000}},
        True, None, "following", rank=2, followed_by=["solana"],
    )
    assert only_sol["chain"] == "Solana"
    assert only_sol["official_follow_total"] == 2
    assert only_sol["follow_count_label"] == "官方关注 1/2"
    assert only_sol["followed_by"] == ["solana"]
    assert only_sol["token_status"] == "未发币"
    assert to_item(
        {"username": "newthing", "name": "New", "description": "Solana app", "public_metrics": {"followers_count": 900}},
        True, None, "following", rank=3, followed_by=["0xmert_"],
    ) is None
    assert to_item(
        {"username": "austin_federa", "name": "Austin Federa", "description": "Head of strategy",
         "public_metrics": {"followers_count": 80000}},
        True, None, "following", rank=4, followed_by=["solana", "toly"],
    ) is None
    assert not keep_unissued_project({
        "username": "alice", "name": "Alice", "description": "working on the protocol",
        "public_metrics": {"followers_count": 1200},
    })[0]
    assert to_item(
        {"username": "coolguy", "name": "coolguy", "description": "", "public_metrics": {}},
        True, None, "following", rank=6, followed_by=["solana"],
    ) is None


def test_launch_and_ambassador_search_queries():
    from web3_radar.collectors.social import AMBASSADOR_QUERIES, LAUNCH_QUERIES

    launch = " ".join(LAUNCH_QUERIES)
    assert '"token launch" OR "fair launch" OR 发射' in launch
    assert "fair launch" in launch
    assert "发射" in launch
    amb = " ".join(AMBASSADOR_QUERIES)
    assert "大使" in amb
    assert "ambassador" in amb.lower()


def test_watch_due_now():
    from datetime import datetime, timedelta, timezone
    from web3_radar.collectors.launch_watch import _is_due

    now = datetime(2026, 8, 26, 4, 0, tzinfo=timezone.utc)
    assert _is_due({"alert": True, "launch_relation": "now"}, now)
    assert not _is_due({"alert": False, "launch_relation": "now"}, now)
    soon = (now + timedelta(seconds=30)).isoformat()
    assert _is_due({"alert": True, "launch_when_utc": soon}, now)
    later = (now + timedelta(hours=5)).isoformat()
    assert not _is_due({"alert": True, "launch_when_utc": later, "launch_relation": "upcoming"}, now)


def test_public_following_parser_requires_real_list():
    from web3_radar.collectors.solana_watch import parse_public_following

    page = """
Title: People followed by @solana
[@solana](https://nitter.example/solana "@solana")
[@toly](https://nitter.example/toly "@toly")
[@helixsvm](https://nitter.example/helixsvm "@helixsvm")
[@nimbusfi](https://nitter.example/nimbusfi "@nimbusfi")
[@orbitprotocol](https://nitter.example/orbitprotocol "@orbitprotocol")
[@zedlabs](https://nitter.example/zedlabs "@zedlabs")
[@quarklayer](https://nitter.example/quarklayer "@quarklayer")
[@mert](https://nitter.example/mert "@mert")
[@jack](https://nitter.example/jack "@jack")
[@staratlas](https://nitter.example/staratlas "@staratlas")
[@orca_so](https://nitter.example/orca_so "@orca_so")
[@solanamobile](https://nitter.example/solanamobile "@solanamobile")
[@therealchaseeb](https://nitter.example/therealchaseeb "@therealchaseeb")
[@Austin_Federa](https://nitter.example/Austin_Federa "@Austin_Federa")
"""
    rows = parse_public_following(page, "solana")
    names = {r["username"] for r in rows}
    assert "helixsvm" in names and "nimbusfi" in names
    assert "orbitprotocol" in names and "zedlabs" in names
    assert "quarklayer" in names
    assert "staratlas" not in names and "orca_so" not in names
    assert "austin_federa" not in names and "therealchaseeb" not in names
    assert "mert" not in names and "jack" not in names
    assert "solana" not in names and "toly" not in names
    assert parse_public_following("Loading...\nAnubis is a compromise", "solana") == []
    assert parse_public_following("random @pumpfun @meme coin page", "solana") == []


def test_collect_social_without_bearer_does_not_crash():
    import asyncio
    rows = asyncio.run(collect_social(["ambassador"], "", 7))
    assert isinstance(rows, list)


def test_news_classifier_keeps_regime_catalysts_only():
    from datetime import datetime, timedelta, timezone
    from web3_radar.collectors.news import classify_headline, parse_calendar_rows, parse_feed_xml

    cut = classify_headline("Fed delivers 25 bps rate cut, markets surge")
    assert cut and cut["bias"] == "偏多" and cut["category"] == "宏观利率"
    hack = classify_headline("Major exchange hacked, $200m drained from hot wallet")
    assert hack and hack["bias"] == "偏空" and hack["category"] == "安全事件"
    depeg = classify_headline("USDT briefly depegs after bank rumor")
    assert depeg and depeg["category"] == "稳定币"
    assert classify_headline("How to buy bitcoin in 2026") is None
    assert classify_headline("Join our web3 hackathon and win prizes") is None
    now = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
    cal = parse_calendar_rows(
        [{
            "title": "CPI y/y",
            "country": "USD",
            "impact": "High",
            "date": (now + timedelta(hours=2)).isoformat(),
            "forecast": "2.9%",
            "previous": "3.0%",
        }],
        now=now,
    )
    assert len(cal) == 1
    assert cal[0]["alert"] is True
    assert cal[0]["impact"] == "高"
    assert cal[0]["bias"] == "方向未定"
    rss = parse_feed_xml(
        """<?xml version="1.0"?><rss><channel>
        <item><title>SEC approves spot bitcoin ETF inflows continue</title>
        <link>https://example.com/etf</link><pubDate>Fri, 21 Aug 2026 10:00:00 GMT</pubDate></item>
        <item><title>Best altcoins to buy this week</title><link>https://example.com/noise</link></item>
        </channel></rss>""",
        "CoinDesk",
    )
    titles = {r["title"] for r in rss}
    assert any("ETF" in t or "etf" in t.lower() for t in titles)
    assert "Best altcoins to buy this week" not in titles
    from web3_radar.collectors.news import synthesize_stance
    long_call = synthesize_stance(
        [
            {"title": "Spot bitcoin ETF inflows hit record", "bias": "偏多", "category": "ETF/机构", "score": 90, "impact": "高", "alert": True, "kind": "新闻"},
            {"title": "Blackrock buying continues", "bias": "偏多", "category": "ETF/机构", "score": 80, "impact": "高", "alert": True, "kind": "新闻"},
        ]
    )
    assert long_call["stance"] == "做多"
    assert long_call["groups"]["long"]
    short_call = synthesize_stance(
        [
            {"title": "Major exchange hacked", "bias": "偏空", "category": "安全事件", "score": 90, "impact": "高", "alert": True, "kind": "新闻"},
            {"title": "USDT depegs", "bias": "偏空", "category": "稳定币", "score": 88, "impact": "高", "alert": True, "kind": "新闻"},
        ]
    )
    assert short_call["stance"] == "做空"
    wait_call = synthesize_stance(
        [
            {"title": "USD CPI y/y", "bias": "方向未定", "category": "宏观利率", "score": 88, "impact": "高", "alert": True, "kind": "日历", "seconds_to": 3600},
            {"title": "ETF inflow", "bias": "偏多", "category": "ETF/机构", "score": 70, "impact": "中", "alert": False, "kind": "新闻"},
        ]
    )
    assert wait_call["stance"] == "观望"


def test_universe_fallbacks_without_coingecko():
    from web3_radar.collectors.binance import builtin_markets, markets_from_coincap, markets_from_binance_tickers, select_perp_universe

    cap = markets_from_coincap({"data": [{"id": "bitcoin", "rank": "1", "symbol": "BTC", "name": "Bitcoin", "marketCapUsd": "2000000000000", "priceUsd": "65000"}]})
    assert cap[0]["id"] == "bitcoin"
    tickers = markets_from_binance_tickers(
        [{"symbol": "BTCUSDT", "quoteVolume": "900", "lastPrice": "65000"}, {"symbol": "ETHUSDT", "quoteVolume": "400", "lastPrice": "3000"}],
        {"BTCUSDT", "ETHUSDT"},
    )
    assert tickers[0]["symbol"] == "btc"
    uni = select_perp_universe(builtin_markets(), {"BTCUSDT", "ETHUSDT", "SOLUSDT"}, set(), limit=5)
    assert uni and uni[0]["binance_symbol"] == "BTCUSDT"
    from web3_radar.collectors.binance import resolve_perp_symbol
    sym, meta = resolve_perp_symbol("btc", uni)
    assert sym == "BTCUSDT"
    pepe, _ = resolve_perp_symbol("PEPE")
    assert pepe in {"PEPEUSDT", "1000PEPEUSDT"}


def test_news_only_keeps_one_day():
    from datetime import datetime, timezone
    from web3_radar.collectors.news import news_is_fresh

    now = datetime(2026, 8, 24, 12, tzinfo=timezone.utc)
    assert news_is_fresh({"seconds_to": 3600}, now)
    assert news_is_fresh({"seconds_to": -20 * 3600}, now)
    assert not news_is_fresh({"seconds_to": -30 * 3600}, now)
    assert not news_is_fresh({"seconds_to": 40 * 3600}, now)
    assert not news_is_fresh({"title": "no time"}, now)


def test_kol_extracts_ca_and_chain():
    from web3_radar.collectors.kol_calls import extract_cas

    evm = extract_cas("aping 0x1234567890abcdef1234567890abcdef12345678 now")
    assert evm and evm[0][1] == "evm"
    sol = extract_cas("CA: So11111111111111111111111111111111111111112")
    assert sol and sol[0][1] == "solana"
    assert not extract_cas("just a wordy sentence without any address")

