from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from web3_radar import db
from web3_radar.collectors.social import (
    AMBASSADOR_QUERIES,
    collect_social,
    extract_deadline,
    looks_like_project_ambassador,
    parse_time,
    score_ambassador,
    twitter_url,
)
from web3_radar.collectors.web3_projects import fetch_ambassador_jobs
from web3_radar.fallback import load_fallback, merge_items


async def scan_ambassadors(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    errors: list[str] = []
    items: list[dict[str, Any]] = []

    social_task = asyncio.wait_for(collect_social(AMBASSADOR_QUERIES, twitter_bearer, lookback_days), timeout=12)
    jobs_task = fetch_ambassador_jobs()
    tweets, jobs = await asyncio.gather(social_task, jobs_task, return_exceptions=True)

    if isinstance(tweets, Exception):
        errors.append(f"twitter: {tweets}")
        tweets = []
    if isinstance(jobs, Exception):
        errors.append(f"jobs: {jobs}")
        jobs = []

    for tw in tweets:
        text = tw.get("text") or ""
        user = tw.get("username") or ""
        if not looks_like_project_ambassador(text, user):
            continue
        created = parse_time(tw.get("_created") or tw.get("created_at"))
        score, priority = score_ambassador(text, created, user)
        project = tw.get("name") or user or "未知项目"
        first_line = text.strip().split("\n")[0][:80]
        items.append(
            {
                "key": str(tw.get("id") or tw.get("url")),
                "project": project,
                "username": user,
                "title": first_line,
                "text": text,
                "url": tw.get("url"),
                "twitter": twitter_url(user),
                "created_at": tw.get("_created") or tw.get("created_at"),
                "deadline": extract_deadline(text),
                "priority": priority.split(" · ")[0],
                "priority_detail": priority,
                "score": score,
                "query": tw.get("_query"),
                "source": "twitter",
                "source_kind": "live",
            }
        )

    live_n = sum(1 for x in items if x.get("source_kind") == "live")
    if not live_n:
        items.extend(jobs)

    manual = await db.cache_get("manual_ambassadors") or []
    if isinstance(manual, list):
        for row in manual:
            item = dict(row)
            item.setdefault("source", "手动")
            item.setdefault("source_kind", "manual")
            items.append(item)

    items.sort(key=lambda x: x.get("score") or 0, reverse=True)
    live_n = sum(1 for x in items if x.get("source_kind") == "live")
    if not live_n:
        items = merge_items(items, load_fallback().get("ambassadors") or [])
        live_n = sum(1 for x in items if x.get("source_kind") == "live")
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "items": items,
        "errors": errors,
        "social_skipped": not bool((twitter_bearer or "").strip()),
        "live_count": live_n,
        "note": (
            "大使只展示近一周项目方发布的招募（检索 大使 / ambassador），个人求职帖不显示。"
            + (" 未配置 Twitter Bearer 时 X 可能为空，已用项目方大使岗位补齐。" if not twitter_bearer else " 已检索 X。")
        ),
    }
