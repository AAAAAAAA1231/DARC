from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.solana_watch import (
    FOLLOW_LOOKBACK_DAYS,
    verified_followers,
    watch_solana_projects,
)


async def scan_launches(twitter_bearer: str = "", lookback_days: int = FOLLOW_LOOKBACK_DAYS) -> dict[str, Any]:
    errors: list[str] = []
    bearer = (twitter_bearer or "").strip()
    days = max(int(lookback_days or 0), FOLLOW_LOOKBACK_DAYS)
    try:
        watch = await watch_solana_projects(bearer, lookback_days=days, group="solana")
    except Exception as exc:
        watch = {"items": [], "alerts": [], "errors": [str(exc)], "scan_stats": []}
        errors.append(str(exc))
    errors.extend(watch.get("errors") or [])
    items = [x for x in (watch.get("items") or []) if verified_followers(x.get("followed_by"))]
    items = [x for x in items if set(x.get("followed_by") or []) <= {"solana", "toly"}]
    items.sort(
        key=lambda x: (
            -(x.get("official_follow_count") or 0),
            not x.get("alert"),
            -(x.get("score") or 0),
        )
    )
    alerts = [x for x in items if x.get("alert")]
    scan_stats = list(watch.get("scan_stats") or [])
    stat_bits = []
    for row in scan_stats:
        acc = row.get("account")
        fetched = int(row.get("fetched") or 0)
        total = int(row.get("following_total") or 0)
        if acc and fetched:
            bit = f"@{acc} 读取最近 {fetched} 个关注"
            if total:
                bit = f"@{acc} 共关注 {total} 个，本次只看最近 {fetched} 个"
            stat_bits.append(bit)
    stats_note = "；".join(stat_bits)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": days,
        "count": len(items),
        "live_count": len(items),
        "follow_count": len(items),
        "sol_count": len(items),
        "bsc_count": 0,
        "onchain_count": 0,
        "new_follow_count": int(watch.get("new_follow_count") or 0),
        "alert_count": len(alerts),
        "alerts": alerts[:12],
        "scan_stats": scan_stats,
        "origin": str(watch.get("origin") or ""),
        "social_skipped": not bool(bearer),
        "items": items,
        "errors": errors,
        "note": (
            "只看 @solana 或 @toly 最近一个月关注、尚未发币的 Web3 项目。个人账号不显示。"
            + ((" " + stats_note + "。") if stats_note else "")
            + (" 当前没有核实到未发币项目。" if not items else "")
        ),
    }
