from __future__ import annotations

from web3_radar.collectors.launch_hunt import (
    parse_bing,
    parse_ddg_lite,
    parse_duckduckgo,
    parse_pub_date,
    parse_rss,
    unwrap_ddg,
)


def test_parse_rss_nitter_status_link():
    xml = """
    <rss><channel>
      <item>
        <title>@alpha: 新项目预售今晚开启 backed by Paradigm</title>
        <link>https://nitter.net/alpha/status/1234567890</link>
        <pubDate>Mon, 01 Sep 2026 08:00:00 GMT</pubDate>
        <description>新项目预售今晚开启</description>
      </item>
    </channel></rss>
    """
    rows = parse_rss(xml, source="nitter-rss")
    assert len(rows) == 1
    assert rows[0]["handle"] == "alpha"
    assert rows[0]["id"] == "1234567890"
    assert rows[0]["url"] == "https://x.com/alpha/status/1234567890"
    assert rows[0]["created_at"] is not None


def test_parse_duckduckgo_and_bing_tweet_links():
    ddg = """
    <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fx.com%2Fvitalikbuterin%2Fstatus%2F99">
      Fair launch of a new project
    </a>
    """
    lite = """
    <a href="https://twitter.com/cobie/status/42">presale going live</a>
    <a href="https://example.com/not-a-tweet">ignore</a>
    """
    bing = """
    <h2><a href="https://x.com/justinsuntron/status/77">新平台发射</a></h2>
    """
    ddg_rows = parse_duckduckgo(ddg)
    lite_rows = parse_ddg_lite(lite)
    bing_rows = parse_bing(bing)
    assert ddg_rows[0]["handle"] == "vitalikbuterin"
    assert lite_rows[0]["handle"] == "cobie"
    assert len(lite_rows) == 1
    assert bing_rows[0]["handle"] == "justinsuntron"
    profile = parse_duckduckgo(
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fx.com%2FKamiraiOfficial">token presale live</a>'
    )
    assert profile[0]["handle"] == "KamiraiOfficial"
    assert "/status/" not in profile[0]["url"]


def test_unwrap_ddg_and_rfc822_date():
    url = unwrap_ddg("https://duckduckgo.com/l/?uddg=https%3A%2F%2Fx.com%2Fa%2Fstatus%2F1&rut=xx")
    assert url.startswith("https://x.com/a/status/1")
    dt = parse_pub_date("Tue, 02 Sep 2026 07:00:00 +0000")
    assert dt is not None
    assert dt.year == 2026
    assert dt.month == 9


def test_brave_parse_and_snowflake_window():
    from datetime import datetime, timezone

    from web3_radar.collectors.launch_hunt import created_from_snowflake, parse_brave

    html = """
    <a href="https://x.com/CoinGapeMedia/status/2084887516784509259">CoinGape on X: "$MELON token presale is live"</a>
    <a href="https://x.com/oldcoin/status/1634222253327142912">old tweet presale</a>
    <a href="https://search.brave.com/search?q=x">ignore</a>
    """
    rows = parse_brave(html)
    ids = {r["id"] for r in rows}
    assert "2084887516784509259" in ids
    assert "1634222253327142912" in ids
    fresh = created_from_snowflake("2084887516784509259")
    old = created_from_snowflake("1634222253327142912")
    assert fresh is not None and fresh.year == 2026
    assert old is not None and old.year == 2023
    assert fresh > datetime(2026, 8, 1, tzinfo=timezone.utc)
