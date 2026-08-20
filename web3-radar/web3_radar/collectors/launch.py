from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.solana_watch import verified_followers, watch_solana_projects


async def scan_launches(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    errors: list[str] = []
    try:
        watch = await watch_solana_projects(twitter_bearer, lookback_days=max(lookback_days, 14))
    except Exception as exc:
        watch = {"items": [], "alerts": [], "errors": [str(exc)]}

    errors.extend(watch.get("errors") or [])
    items = [x for x in (watch.get("items") or []) if verified_followers(x.get("followed_by"))]
    alerts = [x for x in items if x.get("alert")]
    origin = str(watch.get("origin") or "")
    origin_note = {
        "following": "已用 X 接口核实 @solana / @toly / @aeyakovenko 的关注列表。",
        "nitter": "官方接口受限，已用公开镜像关注页核实，仍只保留列表里真实出现的账号。",
    }.get(origin, "")
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "live_count": len(items),
        "follow_count": len(items),
        "new_follow_count": int(watch.get("new_follow_count") or 0),
        "alert_count": len(alerts),
        "alerts": alerts[:12],
        "social_skipped": not bool((twitter_bearer or "").strip()),
        "items": items,
        "errors": errors,
        "note": (
            "只显示已核实被 @solana 或 @toly 关注的项目。观察池、协议目录、随便搜到的推文都不会混进来。"
            + (" " + origin_note if origin_note else "")
            + (" 未填 X 接口令牌时无法核实关注。" if not twitter_bearer else "")
            + (" 当前没有核实到任何关注项目。" if not items else "")
        ),
    }