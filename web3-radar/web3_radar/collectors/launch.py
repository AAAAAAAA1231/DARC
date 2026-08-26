from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.launch_watch import scan_watch_accounts
from web3_radar.collectors.social import (
    LAUNCH_QUERIES,
    collect_social,
    is_mega_brand,
    looks_like_cex_listing,
    looks_like_project_launch,
    parse_time,
    twitter_url,
)
from web3_radar.collectors.solana_watch import (
    FOLLOW_LOOKBACK_DAYS,
    extract_launch_when,
    looks_like_person,
    token_looks_issued,
    verified_followers,
    watch_solana_projects,
)


def _search_item(tw: dict[str, Any]) -> dict[str, Any] | None:
    text = tw.get("text") or ""
    user = tw.get("username") or ""
    if not looks_like_project_launch(text):
        return None
    if looks_like_cex_listing(text) or is_mega_brand(text, user):
        return None
    if looks_like_person(tw.get("name") or user, user, text) and not re_we(text):
        return None
    created = parse_time(tw.get("_created") or tw.get("created_at"))
    timing = extract_launch_when(text, created)
    handle = user or (tw.get("name") or "launch")
    return {
        "key": f"search:{tw.get('id') or handle}:{created or text[:20]}",
        "name": tw.get("name") or handle,
        "username": handle,
        "kind": "检索 · token launch / fair launch / 发射",
        "chain": "Solana",
        "text": text,
        "url": tw.get("url") or twitter_url(handle),
        "twitter": twitter_url(handle),
        "watch_kind": "search",
        "source": "X 检索",
        "source_kind": "search",
        "verified_follow": False,
        "followed_by": [],
        "official_follow_count": 0,
        "token_status": "待核验",
        "alert": bool(timing.get("status")),
        "launch_status": timing.get("status") or "出现发射字眼",
        "launch_when": timing.get("when_cn") or "",
        "launch_when_label": timing.get("label") or "",
        "created_at": tw.get("_created") or tw.get("created_at"),
        "score": 55,
    }


def re_we(text: str) -> bool:
    t = (text or "").lower()
    return any(x in t for x in ("we're", "we are", "our token", "our launch", "我们", "即将发射", "fair launch", "token launch"))


async def _mark_unissued(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    sem = asyncio.Semaphore(4)

    async def one(row: dict[str, Any]) -> dict[str, Any] | None:
        async with sem:
            issued = await token_looks_issued(str(row.get("name") or ""), str(row.get("username") or ""))
            if issued:
                return None
            row = dict(row)
            row["token_status"] = "未发币"
            return row

    checked = await asyncio.gather(*[one(x) for x in items[:50]])
    out.extend([x for x in checked if x])
    out.extend([x for x in items[50:] if x.get("token_status") != "已发币"])
    return out


async def scan_launches(twitter_bearer: str = "", lookback_days: int = FOLLOW_LOOKBACK_DAYS) -> dict[str, Any]:
    errors: list[str] = []
    bearer = (twitter_bearer or "").strip()
    days = max(int(lookback_days or 0), FOLLOW_LOOKBACK_DAYS)
    follow_task = watch_solana_projects(bearer, lookback_days=days, group="solana")
    search_task = asyncio.wait_for(collect_social(LAUNCH_QUERIES, bearer, lookback_days=7), timeout=14)
    watch_task = scan_watch_accounts(bearer)
    follow, tweets, watched = await asyncio.gather(follow_task, search_task, watch_task, return_exceptions=True)
    if isinstance(follow, Exception):
        errors.append(str(follow))
        follow = {"items": [], "alerts": [], "errors": [str(follow)], "scan_stats": []}
    if isinstance(tweets, Exception):
        errors.append(f"search: {tweets}")
        tweets = []
    if isinstance(watched, Exception):
        errors.append(f"watch: {watched}")
        watched = {"items": [], "alerts": [], "errors": [str(watched)], "watches": []}
    errors.extend(follow.get("errors") or [])
    errors.extend(watched.get("errors") or [])

    follow_items = [
        x
        for x in (follow.get("items") or [])
        if verified_followers(x.get("followed_by")) and set(x.get("followed_by") or []) <= {"solana", "toly"}
    ]
    search_items = []
    for tw in tweets or []:
        row = _search_item(tw)
        if row:
            search_items.append(row)
    search_items = await _mark_unissued(search_items)
    watch_items = list(watched.get("items") or [])

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for batch in (follow_items, watch_items, search_items):
        for row in batch:
            key = str(row.get("username") or row.get("key") or "").lower()
            if not key or key in seen:
                continue
            seen.add(key)
            items.append(row)
    items.sort(
        key=lambda x: (
            0 if x.get("source_kind") == "watch" and x.get("alert") else 1,
            0 if x.get("verified_follow") else 1,
            not x.get("alert"),
            -(x.get("official_follow_count") or 0),
            -(x.get("score") or 0),
        )
    )
    alerts = [x for x in items if x.get("alert")]
    scan_stats = list(follow.get("scan_stats") or [])
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": days,
        "count": len(items),
        "live_count": len(items),
        "follow_count": len(follow_items),
        "search_count": len(search_items),
        "watch_count": len(watch_items),
        "sol_count": sum(1 for x in items if "Solana" in str(x.get("chain") or "Solana")),
        "bsc_count": 0,
        "onchain_count": 0,
        "new_follow_count": int(follow.get("new_follow_count") or 0),
        "alert_count": len(alerts),
        "alerts": alerts[:12],
        "scan_stats": scan_stats,
        "watches": watched.get("watches") or [],
        "origin": str(follow.get("origin") or ""),
        "social_skipped": not bool(bearer),
        "items": items,
        "errors": errors,
        "note": (
            "打新两路并行：X 检索 token launch / fair launch / 发射；以及 @solana、@toly 最近一个月新增关注的未发币项目。"
            " 已发币的不跟踪。个人账号不显示。"
            " 自动打新只盯你手动添加的项目方推特，买入卖出都要钱包确认，不会收私钥。"
            + (" 当前没有核实到未发币项目。" if not items else "")
        ),
    }
