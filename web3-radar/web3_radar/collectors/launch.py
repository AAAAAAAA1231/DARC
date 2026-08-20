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
from web3_radar.collectors.solana_watch import watch_solana_projects
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


def _keep_launch_item(row: dict[str, Any]) -> bool:
    if row.get("watch_kind") == "solana_follow":
        return True
    return is_solana(
        row.get("name"),
        row.get("kind"),
        row.get("text"),
        row.get("chain"),
        chains=row.get("chain") or (row.get("extra") or {}).get("chains"),
    )


def _sort_launches(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def key(x: dict[str, Any]) -> tuple:
        rel = {"now": 0, "upcoming": 1, "past": 2, "posted": 3}.get((x.get("extra") or {}).get("timing_rel") or "", 4)
        if x.get("alert"):
            rel = {"正在/刚刚发射": 0, "即将发射": 1, "刚提到发射": 2, "疑似已发射": 3}.get(x.get("launch_status") or "", 2)
        return (
            0 if x.get("alert") else 1,
            rel,
            0 if x.get("new_follow") else 1,
            0 if x.get("watch_kind") == "solana_follow" else 2,
            -(x.get("score") or 0),
        )

    return sorted(items, key=key)


async def scan_launches(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    errors: list[str] = []
    watch_task = watch_solana_projects(twitter_bearer, lookback_days=max(lookback_days, 14))
    social_task = asyncio.wait_for(collect_social(LAUNCH_QUERIES, twitter_bearer, lookback_days), timeout=12)
    proto_task = fetch_new_protocols(lookback_days=45, solana_only=True)
    pretge_task = fetch_pre_tge_projects(solana_only=True)
    watch, tweets, protos, pretge = await asyncio.gather(
        watch_task, social_task, proto_task, pretge_task, return_exceptions=True
    )

    items: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    follow_count = new_follow_count = 0
    origin = ""

    if isinstance(watch, Exception):
        errors.append(f"solana_watch: {watch}")
        watch = {}
    if isinstance(tweets, Exception):
        errors.append(f"twitter: {tweets}")
        tweets = []
    if isinstance(protos, Exception):
        errors.append(f"new_protocols: {protos}")
        protos = []
    if isinstance(pretge, Exception):
        errors.append(f"pre_tge: {pretge}")
        pretge = []

    if isinstance(watch, dict):
        items.extend(watch.get("items") or [])
        alerts = list(watch.get("alerts") or [])
        follow_count = int(watch.get("follow_count") or 0)
        new_follow_count = int(watch.get("new_follow_count") or 0)
        origin = str(watch.get("origin") or "")
        errors.extend(watch.get("errors") or [])

    for tw in tweets:
        row = _tweet_to_item(tw)
        if row:
            items.append(row)
    items.extend(protos)
    items.extend(pretge)

    items = merge_items(items, load_fallback().get("launches") or [])
    items = [x for x in items if _keep_launch_item(x)]
    items = _sort_launches(items)
    live_n = sum(1 for x in items if x.get("source_kind") == "live")
    if not alerts:
        alerts = [x for x in items if x.get("alert")]
    origin_note = {
        "following": "已读取 @solana 最近关注列表。",
        "mention": "关注列表接口受限，已改用 @solana 最近点名的项目。",
        "nitter": "官方接口不可用，已尝试公开镜像上的关注列表。",
    }.get(origin, "")
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "live_count": live_n,
        "follow_count": follow_count,
        "new_follow_count": new_follow_count,
        "alert_count": len(alerts),
        "alerts": alerts[:12],
        "social_skipped": not bool((twitter_bearer or "").strip()),
        "items": items,
        "errors": errors,
        "note": (
            "打新流程：先看 Solana 官方推特最近关注的项目并跟踪，出现 launch / 发射 时标出北京时间。"
            + (" " + origin_note if origin_note else "")
            + (" 未配置 Twitter Bearer 时无法拉关注列表。" if not twitter_bearer else "")
        ),
    }
