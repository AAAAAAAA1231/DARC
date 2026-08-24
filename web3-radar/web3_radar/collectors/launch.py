from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.solana_watch import (
    chain_for_follows,
    follow_badge_text,
    follow_count_label,
    follow_tier_of,
    industry_followers,
    official_follow_total,
    official_followers,
    verified_followers,
    watch_solana_projects,
)


def _merge_launch_items(batches: list[list[dict[str, Any]]]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for batch in batches:
        for row in batch:
            if not verified_followers(row.get("followed_by")):
                continue
            key = (row.get("username") or row.get("key") or "").lower()
            if not key:
                continue
            prev = out.get(key)
            if prev is None:
                out[key] = dict(row)
                continue
            followed = verified_followers(list(prev.get("followed_by") or []) + list(row.get("followed_by") or []))
            prev["followed_by"] = followed
            official = official_followers(followed)
            industry = industry_followers(followed)
            prev["official_follow_count"] = len(official)
            prev["official_follow_total"] = official_follow_total(official)
            prev["industry_follow_count"] = len(industry)
            prev["follow_tier"] = follow_tier_of(followed)
            prev["follow_proof"] = follow_badge_text(followed)
            prev["follow_count_label"] = follow_count_label(followed)
            prev["follow_reason"] = "；".join(
                str(r.get("reason") or "") for r in (prev.get("follow_reasons") or row.get("follow_reasons") or []) if r.get("tier") == "industry"
            ) or row.get("follow_reason") or prev.get("follow_reason") or ""
            if row.get("follow_reasons"):
                seen_h = {str(x.get("handle")) for x in (prev.get("follow_reasons") or [])}
                merged_reasons = list(prev.get("follow_reasons") or [])
                for r in row.get("follow_reasons") or []:
                    if r.get("handle") not in seen_h:
                        merged_reasons.append(r)
                        seen_h.add(r.get("handle"))
                prev["follow_reasons"] = merged_reasons
            prev["chain"] = chain_for_follows(followed, default=str(prev.get("chain") or "Solana"))
            labels = " / ".join(f"@{n}" for n in followed)
            prev["kind"] = f"{labels} 最近关注"
            prev["score"] = max(int(prev.get("score") or 0), int(row.get("score") or 0))
            if row.get("alert") and not prev.get("alert"):
                for field in ("alert", "alert_level", "launch_status", "launch_when", "launch_when_label", "text", "url"):
                    if row.get(field) not in (None, ""):
                        prev[field] = row.get(field)
    return list(out.values())


async def scan_launches(twitter_bearer: str = "", lookback_days: int = 7) -> dict[str, Any]:
    errors: list[str] = []
    bearer = (twitter_bearer or "").strip()
    days = max(lookback_days, 14)
    sol_task = watch_solana_projects(bearer, lookback_days=days, group="solana")
    bsc_task = watch_solana_projects(bearer, lookback_days=days, group="bsc")
    sol_watch, bsc_watch = await asyncio.gather(sol_task, bsc_task, return_exceptions=True)
    if isinstance(sol_watch, Exception):
        errors.append(str(sol_watch))
        sol_watch = {"items": [], "alerts": [], "errors": [str(sol_watch)], "scan_stats": []}
    if isinstance(bsc_watch, Exception):
        errors.append(str(bsc_watch))
        bsc_watch = {"items": [], "alerts": [], "errors": [str(bsc_watch)], "scan_stats": []}
    errors.extend(sol_watch.get("errors") or [])
    errors.extend(bsc_watch.get("errors") or [])
    items = _merge_launch_items([sol_watch.get("items") or [], bsc_watch.get("items") or []])
    items.sort(
        key=lambda x: (
            0 if x.get("follow_tier") == "official" else 1,
            -(x.get("official_follow_count") or 0),
            -(x.get("industry_follow_count") or 0),
            not x.get("alert"),
            -(x.get("score") or 0),
        )
    )
    alerts = [x for x in items if x.get("alert")]
    scan_stats = list(sol_watch.get("scan_stats") or []) + list(bsc_watch.get("scan_stats") or [])
    stat_bits = []
    for row in scan_stats:
        acc = row.get("account")
        fetched = int(row.get("fetched") or 0)
        total = int(row.get("following_total") or 0)
        if acc and fetched:
            bit = f"@{acc} 读取最近 {fetched} 个"
            if total:
                bit = f"@{acc} 共关注 {total} 人，本次读取最近 {fetched} 个"
            stat_bits.append(bit)
    stats_note = "；".join(stat_bits)
    sol_n = sum(1 for x in items if "Solana" in str(x.get("chain") or ""))
    bsc_n = sum(1 for x in items if "BSC" in str(x.get("chain") or ""))
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "count": len(items),
        "live_count": len(items),
        "follow_count": len(items),
        "sol_count": sol_n,
        "bsc_count": bsc_n,
        "onchain_count": 0,
        "new_follow_count": int(sol_watch.get("new_follow_count") or 0) + int(bsc_watch.get("new_follow_count") or 0),
        "alert_count": len(alerts),
        "alerts": alerts[:12],
        "scan_stats": scan_stats,
        "origin": ",".join(x for x in [str(sol_watch.get("origin") or ""), str(bsc_watch.get("origin") or "")] if x),
        "social_skipped": not bool(bearer),
        "items": items,
        "errors": errors,
        "note": (
            "Solana 官方只推 @solana / @toly 正在关注的项目；BSC 官方只推 @cz_binance / @heyibinance。"
            " 另外跟踪 Raj Gokal、Mert、Jupiter、Superteam、PancakeSwap、BNB Chain 等行业名人关注，会单独标记并写明理由，不与官方关注混算。"
            + ((" " + stats_note + "。") if stats_note else "")
            + (" 当前没有核实到任何关注项目。" if not items else "")
        ),
    }
