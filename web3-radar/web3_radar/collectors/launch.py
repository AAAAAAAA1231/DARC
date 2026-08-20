from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.ecosystem import is_solana
from web3_radar.collectors.social import (
    LAUNCH_QUERIES,
    collect_social,
    looks_like_cex_listing,
    looks_like_project_launch,
    looks_like_solana_launch,
    twitter_url,
)
from web3_radar.collectors.web3_projects import fetch_new_protocols, fetch_pre_tge_projects
from web3_radar.fallback import load_fallback, merge_items


def _tweet_to_item(tw: dict[str, Any]) -> dict[str, Any] | None:
    text = tw.get("text") or ""
    if looks_like_cex_listing(text) or not looks_like_project_launch(text):
        return None
    if not looks_like_solana_launch(text):
        return None
    user = tw.get("username") or "未知"
    return {
        "key": f"tw:{tw.get('id') or tw.get('url')}",
        "name": tw.get("name") or user,
        "kind": "Sol X 新项目动态",
        "chain": "Solana",
        "text": text,
        "url": tw.get("url"),
        "twitter": twitter_url(user),
        "created_at": tw.get("_created") or tw.get("created_at"),
        "source": "twitter",
        "source_kind": "live",
        "price_usd": None,
        "extra": tw.get("metrics") or {},
    }


async def scan_launches(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    errors: list[str] = []
    social_task = asyncio.wait_for(collect_social(LAUNCH_QUERIES, twitter_bearer, lookback_days), timeout=12)
    proto_task = fetch_new_protocols(lookback_days=45, solana_only=True)
    pretge_task = fetch_pre_tge_projects(solana_only=True)
    tweets, protos, pretge = await asyncio.gather(social_task, proto_task, pretge_task, return_exceptions=True)

    items: list[dict[str, Any]] = []
    if isinstance(tweets, Exception):
        errors.append(f"twitter: {tweets}")
        tweets = []
    if isinstance(protos, Exception):
        errors.append(f"new_protocols: {protos}")
        protos = []
    if isinstance(pretge, Exception):
        errors.append(f"pre_tge: {pretge}")
        pretge = []

    for tw in tweets:
        row = _tweet_to_item(tw)
        if row:
            items.append(row)
    items.extend(protos)
    items.extend(pretge)

    items = merge_items(items, load_fallback().get("launches") or [])
    items = [
        x
        for x in items
        if is_solana(
            x.get("name"),
            x.get("kind"),
            x.get("text"),
            x.get("chain"),
            chains=x.get("chain") or (x.get("extra") or {}).get("chains"),
        )
    ]
    live_n = sum(1 for x in items if x.get("source_kind") == "live")
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "live_count": live_n,
        "social_skipped": not bool((twitter_bearer or "").strip()),
        "items": items,
        "errors": errors,
        "note": (
            "打新只盯 Solana 生态新项目（X / pump / LaunchLab / 新协议 / 预 TGE），不是交易所上新，也不扫 ETH/BTC 链。"
            + (" 未配置 Twitter Bearer 时 X 检索可能为空，已用 Sol 新协议/预TGE 补齐。" if not twitter_bearer else " 已检索 X。")
        ),
    }
