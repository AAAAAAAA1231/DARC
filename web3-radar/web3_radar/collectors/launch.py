from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.solana_watch import verified_followers, watch_solana_projects


async def scan_launches(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    errors: list[str] = []
    bearer = (twitter_bearer or "").strip()
    try:
        watch = await watch_solana_projects(bearer, lookback_days=max(lookback_days, 14))
    except Exception as exc:
        watch = {"items": [], "alerts": [], "errors": [str(exc)]}
    errors.extend(watch.get("errors") or [])
    items = [x for x in (watch.get("items") or []) if verified_followers(x.get("followed_by"))]
    alerts = [x for x in items if x.get("alert")]
    origin = str(watch.get("origin") or "")
    origin_note = {
        "following": "已用 X 官方关注接口核对。",
        "public_following": "已用公开关注页核对，不是链上新池，也不是观察池。",
    }.get(origin, "")
    stat_bits = []
    for row in watch.get("scan_stats") or []:
        acc = row.get("account")
        fetched = int(row.get("fetched") or 0)
        total = int(row.get("following_total") or 0)
        if acc and fetched:
            bit = f"@{acc} 读取最近 {fetched} 个"
            if total:
                bit = f"@{acc} 共关注 {total} 人，本次读取最近 {fetched} 个"
            stat_bits.append(bit)
    stats_note = "；".join(stat_bits)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "live_count": len(items),
        "follow_count": len(items),
        "onchain_count": 0,
        "new_follow_count": int(watch.get("new_follow_count") or 0),
        "alert_count": len(alerts),
        "alerts": alerts[:12],
        "scan_stats": watch.get("scan_stats") or [],
        "origin": origin,
        "social_skipped": not bool(bearer),
        "items": items,
        "errors": errors,
        "note": (
            "只推出现在 @solana / @toly 关注列表里的项目。不是官方关注的一律不显示，包括链上新池。"
            + (" " + origin_note if origin_note else "")
            + ((" " + stats_note + "。") if stats_note else "")
            + (" 当前没有核实到任何关注项目。" if not items else "")
        ),
    }
