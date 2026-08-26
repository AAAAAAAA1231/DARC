from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from web3_radar import db
from web3_radar.collectors.social import parse_time, twitter_recent_search, twitter_url
from web3_radar.collectors.solana_watch import extract_launch_when, looks_like_launch_alert
from web3_radar.http_util import client as http_client

WATCH_CACHE = "launch_watches_v1"
HANDLE_RE = re.compile(r"^[A-Za-z0-9_]{2,15}$")


def _norm_handle(raw: str) -> str:
    return (raw or "").strip().lstrip("@").split("/")[-1].split("?")[0]


def valid_handle(raw: str) -> str:
    h = _norm_handle(raw)
    if not HANDLE_RE.match(h):
        return ""
    return h


async def list_watches() -> list[dict[str, Any]]:
    rows = await db.cache_get(WATCH_CACHE) or []
    return list(rows) if isinstance(rows, list) else []


async def save_watches(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    await db.cache_set(WATCH_CACHE, rows, 365 * 24 * 3600)
    return rows


async def add_watch(handle: str, note: str = "") -> dict[str, Any]:
    h = valid_handle(handle)
    if not h:
        raise ValueError("请填写项目方推特账号，例如 helixsvm")
    rows = await list_watches()
    for row in rows:
        if str(row.get("handle") or "").lower() == h.lower():
            return row
    item = {
        "handle": h,
        "note": (note or "").strip(),
        "added_at": datetime.now(timezone.utc).isoformat(),
        "twitter": twitter_url(h),
    }
    rows.insert(0, item)
    await save_watches(rows[:40])
    return item


async def remove_watch(handle: str) -> None:
    h = valid_handle(handle)
    rows = [r for r in await list_watches() if str(r.get("handle") or "").lower() != h.lower()]
    await save_watches(rows)


async def _user_tweets_api(bearer: str, handle: str) -> list[dict[str, Any]]:
    if not bearer:
        return []
    return await twitter_recent_search(bearer, f"from:{handle}", max_results=20)


async def _user_tweets_public(handle: str) -> list[dict[str, Any]]:
    urls = (
        f"https://r.jina.ai/https://nitter.tiekoetter.com/{handle}",
        f"https://nitter.tiekoetter.com/{handle}",
    )
    async with http_client(timeout=12.0) as c:
        for url in urls:
            try:
                resp = await c.get(url)
            except Exception:
                continue
            text = resp.text or ""
            if "timeline-item" not in text and "tweet-content" not in text and "status/" not in text.lower():
                continue
            items: list[dict[str, Any]] = []
            blocks = re.split(r'<div class="timeline-item', text)[1:12]
            if not blocks:
                for m in re.finditer(r"https://(?:x|twitter)\.com/" + re.escape(handle) + r"/status/(\d+)[^\n]{0,40}\n(.{20,280})", text, re.I | re.S):
                    items.append(
                        {
                            "id": m.group(1),
                            "text": re.sub(r"\s+", " ", m.group(2)).strip()[:400],
                            "created_at": None,
                            "username": handle,
                            "url": f"https://x.com/{handle}/status/{m.group(1)}",
                        }
                    )
                if items:
                    return items[:12]
                continue
            for block in blocks:
                text_m = re.search(r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>', block, re.S)
                link_m = re.search(r'href="([^"]+/status/\d+)"', block)
                time_m = re.search(r'datetime="([^"]+)"', block)
                if not text_m:
                    continue
                body = re.sub("<[^>]+>", " ", text_m.group(1))
                body = re.sub(r"\s+", " ", body).strip()
                items.append(
                    {
                        "id": (link_m.group(1) if link_m else body[:24]),
                        "text": body,
                        "created_at": time_m.group(1) if time_m else None,
                        "username": handle,
                        "url": ("https://x.com" + link_m.group(1).split("nitter", 1)[-1]) if link_m else twitter_url(handle),
                    }
                )
            if items:
                return items
    return []


async def scan_watch_accounts(twitter_bearer: str = "") -> dict[str, Any]:
    errors: list[str] = []
    watches = await list_watches()
    items: list[dict[str, Any]] = []
    bearer = (twitter_bearer or "").strip()
    for watch in watches:
        handle = str(watch.get("handle") or "")
        tweets: list[dict[str, Any]] = []
        try:
            tweets = await _user_tweets_api(bearer, handle)
            if not tweets:
                tweets = await _user_tweets_public(handle)
        except Exception as exc:
            errors.append(f"@{handle}: {exc}")
            continue
        best = None
        for tw in tweets:
            text = tw.get("text") or ""
            if not looks_like_launch_alert(text):
                continue
            created = parse_time(tw.get("created_at"))
            timing = extract_launch_when(text, created)
            row = {
                "key": f"watch:{handle}:{(tw.get('id') or timing.get('when_utc') or text[:24])}",
                "name": handle,
                "username": handle,
                "kind": "盯盘推特",
                "chain": "Solana",
                "text": text,
                "url": tw.get("url") or twitter_url(handle),
                "twitter": twitter_url(handle),
                "watch_kind": "manual_watch",
                "source": "手动盯盘",
                "source_kind": "watch",
                "verified_follow": False,
                "followed_by": [],
                "token_status": "待核验",
                "alert": True,
                "launch_status": timing.get("status") or "出现发射字眼",
                "launch_when": timing.get("when_cn") or "",
                "launch_when_label": timing.get("label") or "",
                "created_at": tw.get("created_at"),
                "sell_hint": "发币后是否卖出请你自己在钱包里确认。本程序不会使用私钥下单。",
            }
            if best is None or str(timing.get("when_utc") or "") > str((best.get("created_at") or "")):
                best = row
        if best:
            items.append(best)
        elif tweets:
            items.append(
                {
                    "key": f"watch:{handle}:idle",
                    "name": handle,
                    "username": handle,
                    "kind": "盯盘推特",
                    "chain": "Solana",
                    "text": f"正在盯 @{handle}。尚未读到明确的发射时间。",
                    "url": twitter_url(handle),
                    "twitter": twitter_url(handle),
                    "watch_kind": "manual_watch",
                    "source": "手动盯盘",
                    "source_kind": "watch",
                    "verified_follow": False,
                    "followed_by": [],
                    "token_status": "跟踪中",
                    "alert": False,
                    "launch_status": "跟踪中（尚未提到发射）",
                    "launch_when_label": "等待项目方公布时间",
                    "sell_hint": "本程序不会索取或使用私钥。",
                }
            )
    return {
        "watches": watches,
        "items": items,
        "alerts": [x for x in items if x.get("alert")],
        "errors": errors,
        "note": "只盯你手动添加的项目方推特。出现发射时间会换成北京时间。链上买入/卖出一律要钱包确认，不会收私钥。",
    }
