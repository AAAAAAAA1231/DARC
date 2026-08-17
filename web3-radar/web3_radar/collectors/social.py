from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import quote_plus

import httpx

TWITTER_SEARCH = "https://api.twitter.com/2/tweets/search/recent"
NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
]

AMBASSADOR_QUERIES = [
    "web3 ambassador program",
    "crypto ambassador recruitment",
    "招募大使 web3",
    "大使计划 crypto",
    "community ambassador blockchain apply",
    "we are hiring ambassadors web3",
]

LAUNCH_QUERIES = [
    "打新",
    "新平台 launch",
    "crypto presale",
    "IDO launchpad",
    "IEO launch",
    "token launch tomorrow",
    "presale live",
    "fair launch mint",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _within_days(dt: datetime | None, days: int) -> bool:
    if dt is None:
        return True
    return dt >= _now() - timedelta(days=days)


def parse_time(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        ts = value / 1000 if value > 10_000_000_000 else value
        try:
            return datetime.fromtimestamp(ts, tz=timezone.utc)
        except (OSError, ValueError):
            return None
    text = str(value)
    for fmt in ("%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text.replace("+00:00", "Z"), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


async def twitter_recent_search(bearer: str, query: str, max_results: int = 20) -> list[dict[str, Any]]:
    if not bearer:
        return []
    headers = {"Authorization": f"Bearer {bearer}"}
    params = {
        "query": f"({query}) -is:retweet lang:en OR lang:zh",
        "max_results": str(max(10, min(max_results, 100))),
        "tweet.fields": "created_at,lang,public_metrics,entities,author_id",
        "expansions": "author_id",
        "user.fields": "username,name,public_metrics",
    }
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(TWITTER_SEARCH, headers=headers, params=params)
        if resp.status_code >= 400:
            return []
        data = resp.json()
    users = {u["id"]: u for u in (data.get("includes") or {}).get("users", [])}
    out = []
    for tw in data.get("data") or []:
        user = users.get(tw.get("author_id"), {})
        out.append(
            {
                "id": tw.get("id"),
                "text": tw.get("text"),
                "created_at": tw.get("created_at"),
                "username": user.get("username", ""),
                "name": user.get("name", ""),
                "url": f"https://x.com/{user.get('username', 'i')}/status/{tw.get('id')}",
                "metrics": tw.get("public_metrics") or {},
            }
        )
    return out


async def nitter_search(query: str) -> list[dict[str, Any]]:
    """Best-effort public HTML search; silently skip dead instances."""
    encoded = quote_plus(query)
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers={"User-Agent": "ChainRadar/1.0"}) as client:
        for base in NITTER_INSTANCES:
            try:
                resp = await client.get(f"{base}/search", params={"f": "tweets", "q": query})
                if resp.status_code != 200 or "tweet-content" not in resp.text:
                    continue
                items = []
                blocks = re.split(r'<div class="timeline-item', resp.text)[1:16]
                for block in blocks:
                    text_m = re.search(r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>', block, re.S)
                    user_m = re.search(r'class="username"[^>]*>@([^<]+)', block)
                    link_m = re.search(r'href="([^"]+/status/\d+)"', block)
                    time_m = re.search(r'datetime="([^"]+)"', block)
                    if not text_m:
                        continue
                    text = re.sub("<[^>]+>", " ", text_m.group(1))
                    text = re.sub(r"\s+", " ", text).strip()
                    items.append(
                        {
                            "id": (link_m.group(1) if link_m else text[:24]),
                            "text": text,
                            "created_at": time_m.group(1) if time_m else None,
                            "username": user_m.group(1) if user_m else "",
                            "name": "",
                            "url": (base + link_m.group(1)) if link_m else base,
                            "metrics": {},
                        }
                    )
                if items:
                    return items
            except Exception:
                continue
    return []


def score_ambassador(text: str, created: datetime | None) -> tuple[int, str]:
    t = text.lower()
    score = 40
    reasons = []
    if any(k in t for k in ("deadline", "截止", "closes", "until", "before")):
        score += 15
        reasons.append("含截止时间")
    if any(k in t for k in ("paid", "stipend", "salary", "grant", "奖励", "薪资", "usdt")):
        score += 20
        reasons.append("含报酬")
    if any(k in t for k in ("apply", "application", "form", "报名", "申请", "typeform", "google form")):
        score += 15
        reasons.append("含申请入口")
    if any(k in t for k in ("tier-1", "binance", "okx", "coinbase", "l2", "mainnet")):
        score += 10
        reasons.append("头部生态")
    if created and created >= _now() - timedelta(days=2):
        score += 10
        reasons.append("48h 内发布")
    score = min(100, score)
    if score >= 75:
        priority = "高"
    elif score >= 55:
        priority = "中"
    else:
        priority = "低"
    return score, priority + (" · " + "、".join(reasons) if reasons else "")


def extract_deadline(text: str) -> str:
    patterns = [
        r"deadline[:\s]+([A-Za-z]{3,9}\s+\d{1,2})",
        r"截止[于到：:\s]*([\d]{1,2}[月./-][\d]{1,2}[日号]?)",
        r"until\s+([A-Za-z]{3,9}\s+\d{1,2})",
        r"closes?\s+on\s+([A-Za-z0-9,\s]+)",
        r"(\d{4}-\d{2}-\d{2})",
    ]
    for p in patterns:
        m = re.search(p, text, re.I)
        if m:
            return m.group(1).strip()
    return "一周内（默认窗口）"


async def collect_social(queries: list[str], bearer: str, lookback_days: int) -> list[dict[str, Any]]:
    """Search recent posts. Without a Bearer token, skip Nitter — it is usually dead in CN and burns 10s+."""
    if not (bearer or "").strip():
        return []
    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for q in queries:
        tweets = await twitter_recent_search(bearer, q)
        for tw in tweets:
            created = parse_time(tw.get("created_at"))
            if not _within_days(created, lookback_days):
                continue
            key = str(tw.get("id") or tw.get("url") or tw.get("text"))[:80]
            if key in seen:
                continue
            seen.add(key)
            tw["_query"] = q
            tw["_created"] = created.isoformat() if created else None
            items.append(tw)
    return items
