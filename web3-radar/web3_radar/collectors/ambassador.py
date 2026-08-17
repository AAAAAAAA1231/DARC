from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from web3_radar import db
from web3_radar.collectors.social import (
    AMBASSADOR_QUERIES,
    collect_social,
    extract_deadline,
    score_ambassador,
)
from web3_radar.fallback import load_fallback, merge_items


async def scan_ambassadors(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    errors: list[str] = []
    items: list[dict[str, Any]] = []
    social_skipped = not bool((twitter_bearer or "").strip())
    if social_skipped:
        note = "未配置 X_BEARER_TOKEN，已跳过 Twitter/Nitter（国内通常不可达）。下面是观察池，也可手动添加。"
    else:
        try:
            tweets = await asyncio.wait_for(
                collect_social(AMBASSADOR_QUERIES, twitter_bearer, lookback_days),
                timeout=12,
            )
        except Exception as exc:
            tweets = []
            errors.append(f"twitter: {exc}")
        for tw in tweets:
            text = tw.get("text") or ""
            score, priority = score_ambassador(text, None)
            project = tw.get("name") or tw.get("username") or "未知项目"
            first_line = text.strip().split("\n")[0][:80]
            items.append(
                {
                    "key": str(tw.get("id") or tw.get("url")),
                    "project": project,
                    "username": tw.get("username"),
                    "title": first_line,
                    "text": text,
                    "url": tw.get("url"),
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
        note = "已检索 Twitter。观察池条目会排在实时帖文后面。"

    manual = await db.cache_get("manual_ambassadors") or []
    if isinstance(manual, list):
        for row in manual:
            item = dict(row)
            item.setdefault("source", "手动")
            item.setdefault("source_kind", "manual")
            items.append(item)

    items.sort(key=lambda x: x.get("score") or 0, reverse=True)
    seed = load_fallback().get("ambassadors") or []
    items = merge_items(items, seed)
    live_n = sum(1 for x in items if x.get("source_kind") == "live")
    seed_n = sum(1 for x in items if x.get("fallback") or x.get("source_kind") in {"seed", None} and x.get("source") == "观察池")
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "items": items,
        "errors": errors,
        "social_skipped": social_skipped,
        "live_count": live_n,
        "seed_count": seed_n,
        "note": note,
    }
