from __future__ import annotations

from datetime import datetime, timedelta, timezone

from web3_radar.engine.launch_rank import rank_launch_items, score_launch_item


NOW = datetime(2026, 9, 2, 12, 0, tzinfo=timezone.utc)


def test_vc_mention_outranks_plain_presale():
    vc = score_launch_item(
        text="New project presale live, backed by Paradigm and a16z",
        handle="randomlab",
        created_at=NOW - timedelta(hours=6),
        now=NOW,
    )
    plain = score_launch_item(
        text="presale live for a new meme",
        handle="someone",
        created_at=NOW - timedelta(hours=6),
        now=NOW,
    )
    assert vc["institutions"] == ["Paradigm", "a16z"]
    assert vc["score"] > plain["score"]
    assert any("机构" in r for r in vc["reasons"])


def test_notable_handle_boosts_score():
    notable = score_launch_item(
        text="Fair launch tomorrow",
        handle="elonmusk",
        created_at=NOW - timedelta(hours=2),
        now=NOW,
    )
    nobody = score_launch_item(
        text="Fair launch tomorrow",
        handle="unknownacct99",
        created_at=NOW - timedelta(hours=2),
        now=NOW,
    )
    assert notable["notable"] == "Elon Musk"
    assert notable["score"] > nobody["score"]


def test_rank_orders_vc_then_kol_and_drops_old_and_cex():
    rows = rank_launch_items(
        [
            {
                "id": "old",
                "handle": "cz_binance",
                "text": "presale for a new project backed by Binance Labs",
                "created_at": NOW - timedelta(days=40),
            },
            {
                "id": "rocket",
                "handle": "spacefan",
                "text": "今晚文昌发射场，长征7号升空后飞行过程出现异常",
                "created_at": NOW - timedelta(hours=4),
            },
            {
                "id": "listing",
                "handle": "binancezh",
                "text": "Binance will list FOO/USDT spot listing tomorrow",
                "created_at": NOW - timedelta(hours=3),
            },
            {
                "id": "plain",
                "handle": "degenxyz",
                "text": "新项目预售今晚开启",
                "created_at": NOW - timedelta(days=2),
            },
            {
                "id": "vc",
                "handle": "thedefiedge",
                "text": "发射了，Paradigm 领投的新平台 presale",
                "created_at": NOW - timedelta(hours=5),
            },
            {
                "id": "kol",
                "handle": "blknoiz06",
                "text": "newproject fair launch going live",
                "created_at": NOW - timedelta(hours=8),
            },
        ],
        now=NOW,
        lookback_days=30,
    )
    ids = [r["id"] for r in rows]
    assert "old" not in ids
    assert "rocket" not in ids
    assert "listing" not in ids
    assert ids[0] == "vc"
    assert rows[0]["score"] >= rows[1]["score"]
    assert "kol" in ids and "plain" in ids


def test_drops_rocket_and_profile_chrome():
    from web3_radar.engine.launch_rank import looks_like_crypto_launch

    assert looks_like_crypto_launch("Fair Launch (@FairLaunch) / Posts / X") is False
    assert looks_like_crypto_launch("presale1000x Crypto Pre-Sale 1000X (@Presale1000x) / X") is False
    assert looks_like_crypto_launch("LaunchXToken LaunchX (@LaunchXToken) on X") is False
    assert looks_like_crypto_launch("今晚文昌发射场，长征7号升空") is False
    assert looks_like_crypto_launch("新项目预售今晚开启") is True
