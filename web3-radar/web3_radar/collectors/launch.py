from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.meme import fetch_dexscreener_search, fetch_pumpfun
from web3_radar.collectors.social import LAUNCH_QUERIES, collect_social

KEYWORDS = ("打新", "新平台", "launch", "presale", "ido", "ieo", "launchpad", "fair launch", "mint")


def _is_launch_text(text: str) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in KEYWORDS)


async def scan_launches(twitter_bearer: str = "", lookback_days: int = 5) -> dict[str, Any]:
    tweets_task = collect_social(LAUNCH_QUERIES, twitter_bearer, lookback_days)
    dex_task = fetch_dexscreener_search("presale")
    pump_task = fetch_pumpfun(30)
    tweets, dex, pump = await asyncio.gather(tweets_task, dex_task, pump_task, return_exceptions=True)
    items: list[dict[str, Any]] = []
    errors: list[str] = []

    if isinstance(tweets, Exception):
        errors.append(f"twitter: {tweets}")
        tweets = []
    if isinstance(dex, Exception):
        errors.append(f"dex: {dex}")
        dex = []
    if isinstance(pump, Exception):
        errors.append(f"pump: {pump}")
        pump = []

    for tw in tweets:
        text = tw.get("text") or ""
        if not _is_launch_text(text):
            continue
        items.append(
            {
                "key": f"tw:{tw.get('id') or tw.get('url')}",
                "name": tw.get("username") or "未知",
                "kind": "社媒打新",
                "chain": "未知",
                "text": text,
                "url": tw.get("url"),
                "created_at": tw.get("_created") or tw.get("created_at"),
                "source": "twitter",
                "price_usd": None,
                "extra": tw.get("metrics") or {},
            }
        )

    for pair in dex[:40]:
        items.append(
            {
                "key": f"dex:{pair.get('key')}",
                "name": f"{pair.get('symbol')} / {pair.get('name')}",
                "kind": "新池/上线",
                "chain": pair.get("chain"),
                "text": f"流动性 ${pair.get('liquidity_usd', 0):,.0f} · 1h 成交 ${pair.get('volume_h1', 0):,.0f}",
                "url": pair.get("url"),
                "created_at": pair.get("created_at"),
                "source": "dexscreener",
                "price_usd": pair.get("price_usd"),
                "extra": pair,
            }
        )

    for coin in pump[:30]:
        items.append(
            {
                "key": f"pump:{coin.get('key')}",
                "name": f"{coin.get('symbol')} / {coin.get('name')}",
                "kind": "Pump.fun 新盘",
                "chain": "Solana",
                "text": f"持币地址 {coin.get('holders')} · FDV ${coin.get('fdv', 0):,.0f}",
                "url": coin.get("url"),
                "created_at": coin.get("created_at"),
                "source": "pump.fun",
                "price_usd": coin.get("price_usd"),
                "extra": coin,
            }
        )

    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "items": items,
        "errors": errors,
    }
