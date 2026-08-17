from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.social import (
    AMBASSADOR_QUERIES,
    collect_social,
    extract_deadline,
    score_ambassador,
)
from web3_radar.fallback import load_fallback, merge_items


async def scan_ambassadors(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    try:
        tweets = await asyncio.wait_for(collect_social(AMBASSADOR_QUERIES, twitter_bearer, lookback_days), timeout=12)
    except Exception:
        tweets = []
    items = []
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
            }
        )
    items.sort(key=lambda x: x["score"], reverse=True)
    seed = load_fallback().get("ambassadors") or []
    items = merge_items(items, seed)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "items": items,
        "note": "国内网络常无法访问 Twitter。已同时给出观察池；填写 Twitter Bearer 可补充实时帖文。",
    }
