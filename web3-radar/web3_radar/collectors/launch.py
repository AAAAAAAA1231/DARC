from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.solana_onchain import scan_onchain_launches
from web3_radar.collectors.solana_watch import verified_followers, watch_solana_projects


async def scan_launches(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    errors: list[str] = []
    bearer = (twitter_bearer or "").strip()
    follow_items: list[dict[str, Any]] = []
    scan_stats: list[dict[str, Any]] = []
    origin = ""

    try:
        watch = await watch_solana_projects(bearer, lookback_days=max(lookback_days, 14))
    except Exception as exc:
        watch = {"items": [], "alerts": [], "errors": [str(exc)]}
    errors.extend(watch.get("errors") or [])
    scan_stats = list(watch.get("scan_stats") or [])
    origin = str(watch.get("origin") or "")
    follow_items = [x for x in (watch.get("items") or []) if verified_followers(x.get("followed_by"))]

    try:
        onchain = await scan_onchain_launches()
    except Exception as exc:
        onchain = {"items": [], "errors": [str(exc)]}
    errors.extend(onchain.get("errors") or [])
    pool_items = [x for x in (onchain.get("items") or []) if x.get("watch_kind") == "onchain_pool" and not x.get("verified_follow")]

    items = follow_items + pool_items
    items.sort(
        key=lambda x: (
            not x.get("verified_follow"),
            not x.get("alert"),
            -(x.get("score") or 0),
        )
    )
    alerts = [x for x in items if x.get("alert")]
    stat_bits = []
    for row in scan_stats:
        acc = row.get("account")
        fetched = int(row.get("fetched") or 0)
        total = int(row.get("following_total") or 0)
        if acc and fetched:
            stat_bits.append(f"@{acc} 共关注 {total} 人，本次读取最近 {fetched} 个")
    follow_note = ""
    if bearer and follow_items:
        follow_note = " 另已核对官方关注：" + "；".join(stat_bits) + "。" if stat_bits else " 另已核对官方关注列表。"
    elif bearer:
        follow_note = " 已尝试核对官方关注，但当前没有核实到。"
    if not bearer:
        skip_bits = ("未配置 X 接口令牌", "没有从官方关注列表核实到项目")
        errors = [e for e in errors if not any(bit in str(e) for bit in skip_bits)]
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "live_count": len(items),
        "follow_count": len(follow_items),
        "onchain_count": len(pool_items),
        "new_follow_count": int(watch.get("new_follow_count") or 0),
        "alert_count": len(alerts),
        "alerts": alerts[:12],
        "scan_stats": scan_stats,
        "origin": origin,
        "social_skipped": not bool(bearer),
        "items": items,
        "errors": errors,
        "note": (
            "默认显示 Solana 链上新开盘（GeckoTerminal / Pump.fun / DexScreener），"
            "这些不是 @solana 或 @toly 的关注。"
            + follow_note
            + (" 未填 X 令牌不影响链上打新。" if not bearer else "")
            + (" 当前没有拉到新池。" if not items else "")
        ),
    }
