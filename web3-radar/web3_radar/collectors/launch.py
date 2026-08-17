from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from web3_radar.fallback import load_fallback, merge_items
from web3_radar.collectors.meme import fetch_dexscreener_search, fetch_geckoterminal, fetch_pumpfun
from web3_radar.collectors.social import LAUNCH_QUERIES, collect_social
from web3_radar.http_util import client as http_client

KEYWORDS = ("打新", "新平台", "launch", "presale", "ido", "ieo", "launchpad", "fair launch", "mint")
OKX_ANN = "https://www.okx.com/api/v5/support/announcements"
LISTING_RE = re.compile(r"\b([A-Z0-9]{2,15})/(USDT|USD|USDC)\b")


def _is_launch_text(text: str) -> bool:
    t = text.lower()
    return any(k.lower() in t for k in KEYWORDS)


def parse_okx_listing(row: dict[str, Any]) -> dict[str, Any] | None:
    title = str(row.get("title") or "").strip()
    url = str(row.get("url") or "").strip()
    if not title:
        return None
    m = LISTING_RE.search(title)
    base = m.group(1) if m else title.split()[0][:16]
    quote = m.group(2) if m else ""
    raw_ts = row.get("pTime") or row.get("businessPTime")
    created = None
    try:
        ts = int(str(raw_ts))
        if ts > 10_000_000_000:
            ts = ts / 1000
        created = datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        created = None
    return {
        "key": f"okx:{base}:{quote or 'spot'}:{row.get('pTime') or title}",
        "name": f"{base}{'/' + quote if quote else ''} · OKX 上新",
        "kind": "交易所打新",
        "chain": "OKX",
        "text": title,
        "url": url or "https://www.okx.com/zh-hans/help/section/announcements-new-listings",
        "created_at": created,
        "source": "OKX 公告",
        "source_kind": "live",
        "price_usd": None,
        "extra": {"base": base, "quote": quote, "title": title},
    }


async def fetch_okx_new_listings(limit: int = 24) -> list[dict[str, Any]]:
    async with http_client(timeout=12.0) as c:
        resp = await c.get(
            OKX_ANN,
            params={"annType": "announcements-new-listings"},
            headers={"Accept-Language": "zh-CN"},
        )
        resp.raise_for_status()
        payload = resp.json()
    details = ((payload.get("data") or [{}])[0].get("details") or []) if isinstance(payload, dict) else []
    cutoff = datetime.now(timezone.utc) - timedelta(days=21)
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for row in details:
        item = parse_okx_listing(row)
        if not item:
            continue
        created = item.get("created_at")
        if created:
            try:
                dt = datetime.fromisoformat(created)
                if dt < cutoff:
                    continue
            except ValueError:
                pass
        base = (item.get("extra") or {}).get("base") or item["name"]
        if base in seen:
            continue
        seen.add(base)
        out.append(item)
        if len(out) >= limit:
            break
    return out


async def scan_launches(twitter_bearer: str = "", lookback_days: int = 5) -> dict[str, Any]:
    social_skipped = not bool((twitter_bearer or "").strip())
    tasks: list[Any] = [
        fetch_okx_new_listings(),
        fetch_dexscreener_search("presale"),
        fetch_pumpfun(30),
        fetch_geckoterminal(),
    ]
    if not social_skipped:
        tasks.append(asyncio.wait_for(collect_social(LAUNCH_QUERIES, twitter_bearer, lookback_days), timeout=12))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    okx, dex, pump, gecko = results[0], results[1], results[2], results[3]
    tweets: list[dict[str, Any]] = []
    if not social_skipped:
        tweets = results[4]  # type: ignore[misc]

    items: list[dict[str, Any]] = []
    errors: list[str] = []

    if isinstance(okx, Exception):
        errors.append(f"okx: {okx}")
        okx = []
    if isinstance(tweets, Exception):
        errors.append(f"twitter: {tweets}")
        tweets = []
    if isinstance(dex, Exception):
        errors.append(f"dex: {dex}")
        dex = []
    if isinstance(pump, Exception):
        errors.append(f"pump: {pump}")
        pump = []
    if isinstance(gecko, Exception):
        errors.append(f"gecko: {gecko}")
        gecko = []

    items.extend(okx)

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
                "source_kind": "live",
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
                "source_kind": "live",
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
                "source_kind": "live",
                "price_usd": coin.get("price_usd"),
                "extra": coin,
            }
        )

    for coin in gecko[:30]:
        items.append(
            {
                "key": f"gt:{coin.get('key')}",
                "name": f"{coin.get('symbol')} / {coin.get('name')}",
                "kind": "热门新池",
                "chain": coin.get("chain"),
                "text": f"流动性 ${coin.get('liquidity_usd', 0):,.0f} · 价格 {coin.get('price_usd')}",
                "url": coin.get("url"),
                "created_at": coin.get("created_at"),
                "source": "geckoterminal",
                "source_kind": "live",
                "price_usd": coin.get("price_usd"),
                "extra": coin,
            }
        )

    items = merge_items(items, load_fallback().get("launches") or [])
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "okx_count": len(okx) if isinstance(okx, list) else 0,
        "social_skipped": social_skipped,
        "items": items,
        "errors": errors,
        "note": (
            "国内跳过 Twitter。" if social_skipped else "已尝试检索 Twitter。"
        )
        + " 打新优先看 OKX 上新公告，链上新池仅供参考。",
    }
