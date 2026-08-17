from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.social import (
    AMBASSADOR_QUERIES,
    collect_social,
    extract_deadline,
    score_ambassador,
)


async def scan_ambassadors(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    tweets = await collect_social(AMBASSADOR_QUERIES, twitter_bearer, lookback_days)
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
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "items": items,
        "note": "未配置 Twitter Bearer 时将尝试公共镜像；建议在设置中填入 API Token 以提高覆盖率。",
    }
