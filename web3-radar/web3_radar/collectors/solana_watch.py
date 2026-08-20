from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

from web3_radar.collectors.social import (
    NITTER_INSTANCES,
    is_mega_brand,
    parse_time,
    twitter_url,
)
from web3_radar.http_util import client as http_client

CN = timezone(timedelta(hours=8))
TWITTER_API = "https://api.twitter.com/2"
SOLANA_HANDLE = "solana"
SKIP_HANDLES = {
    "solana",
    "solanalabs",
    "solanastatus",
    "solanafdsn",
    "solanafndn",
    "binance",
    "binancezh",
    "coinbase",
    "okx",
    "bybit_official",
    "ethereum",
}

LAUNCH_ALERT_HINTS = (
    "launch",
    "launched",
    "launching",
    "launches",
    "fair launch",
    "stealth launch",
    "token generation",
    "tge",
    "now live",
    "going live",
    "is live",
    "mint is live",
    "presale",
    "public sale",
    "发射",
    "上线",
    "开盘",
    "开打",
    "公售",
    "主网上线",
)

WELCOME_HINTS = (
    "welcome",
    "welcoming",
    "joined",
    "joining",
    "built on",
    "on solana",
    "ecosystem",
    "congrats",
    "shipped",
    "now live on solana",
    "gm ",
)

_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def fmt_cn(dt: datetime | None) -> str:
    if not dt:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(CN).strftime("%Y-%m-%d %H:%M") + " 北京时间"


def looks_like_launch_alert(text: str) -> bool:
    t = (text or "").lower()
    if not any(h in t for h in LAUNCH_ALERT_HINTS):
        return False
    if re.search(r"\b(binance|okx|bybit|coinbase)\b.+\b(list|listing|launchpool)\b", t):
        return False
    return True


def extract_mentions(text: str, extra: list[str] | None = None) -> list[str]:
    names = [m.group(1).lower() for m in re.finditer(r"@([A-Za-z0-9_]{2,15})", text or "")]
    for item in extra or []:
        n = str(item or "").strip().lstrip("@").lower()
        if n:
            names.append(n)
    out: list[str] = []
    seen: set[str] = set()
    for n in names:
        if n in SKIP_HANDLES or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def _parse_clock(blob: str) -> tuple[int, int] | None:
    m = re.search(r"\b(\d{1,2}):(\d{2})\s*(am|pm)?\b", blob, re.I)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        ampm = (m.group(3) or "").lower()
    else:
        m = re.search(r"\b(\d{1,2})\s*(am|pm)\b", blob, re.I)
        if m:
            hour, minute, ampm = int(m.group(1)), 0, m.group(2).lower()
        else:
            m = re.search(r"(\d{1,2})\s*[点时](?:\s*(\d{1,2})\s*分?)?", blob)
            if not m:
                return None
            hour, minute, ampm = int(m.group(1)), int(m.group(2) or 0), ""
    if ampm == "pm" and hour < 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    if hour > 23 or minute > 59:
        return None
    return hour, minute


def extract_launch_when(
    text: str,
    tweeted_at: datetime | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Pull an explicit launch time from the tweet, else fall back to when it was posted."""
    now = now or datetime.now(timezone.utc)
    posted = tweeted_at if tweeted_at else now
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    t = text or ""
    when: datetime | None = None
    source = "tweet"

    rel = re.search(r"(?:in|within)\s+(\d+)\s*(hours?|hrs?|minutes?|mins?|days?)", t, re.I)
    if not rel:
        rel = re.search(r"(\d+)\s*(小时|分钟|天)\s*后", t)
    if rel:
        n = int(rel.group(1))
        unit = rel.group(2).lower()
        if "分" in unit or unit.startswith("min"):
            when = posted + timedelta(minutes=n)
        elif "天" in unit or unit.startswith("day"):
            when = posted + timedelta(days=n)
        else:
            when = posted + timedelta(hours=n)
        source = "relative"

    if when is None:
        iso = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[ T](\d{1,2}):(\d{2}))?", t)
        if iso:
            when = datetime(
                int(iso.group(1)), int(iso.group(2)), int(iso.group(3)),
                int(iso.group(4) or 0), int(iso.group(5) or 0), tzinfo=timezone.utc,
            )
            source = "date"

    if when is None:
        md = re.search(
            r"\b(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
            r"jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
            r"\s+(\d{1,2})(?:,?\s*(\d{4}))?",
            t, re.I,
        )
        if md:
            month = _MONTHS[md.group(1).lower()[:3] if md.group(1).lower() != "sept" else "sep"]
            day = int(md.group(2))
            year = int(md.group(3) or posted.year)
            hour, minute = _parse_clock(t[md.end(): md.end() + 48]) or (0, 0)
            try:
                when = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
                source = "date"
            except ValueError:
                when = None

    if when is None:
        cn = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?(?:\s*(\d{1,2})\s*[点时:：]\s*(\d{1,2})?)?", t)
        if cn:
            year = posted.astimezone(CN).year
            hour = int(cn.group(3) or 0)
            minute = int(cn.group(4) or 0)
            try:
                when = datetime(year, int(cn.group(1)), int(cn.group(2)), hour, minute, tzinfo=CN).astimezone(timezone.utc)
                source = "date"
            except ValueError:
                when = None

    if when is None and re.search(r"\b(tomorrow|明日|明天)\b", t, re.I):
        clock = _parse_clock(t) or (0, 0)
        base = posted.astimezone(CN) + timedelta(days=1)
        when = base.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0).astimezone(timezone.utc)
        source = "relative"
    elif when is None and re.search(r"\b(today|tonight|this evening|今日|今天|今晚)\b", t, re.I):
        clock = _parse_clock(t)
        base = posted.astimezone(CN)
        if clock:
            when = base.replace(hour=clock[0], minute=clock[1], second=0, microsecond=0).astimezone(timezone.utc)
        else:
            when = posted
        source = "relative"

    if when is None:
        when = posted
        source = "posted"

    delta = when - now
    if source == "posted":
        status = "刚提到发射"
        relation = "posted"
        label = f"发现时间 {fmt_cn(when)}（推文未写具体发射时刻）"
    elif delta >= timedelta(minutes=40):
        status = "即将发射"
        relation = "upcoming"
        label = f"预计 {fmt_cn(when)}"
    elif delta <= timedelta(hours=-6):
        status = "疑似已发射"
        relation = "past"
        label = f"标注时间 {fmt_cn(when)}"
    else:
        status = "正在/刚刚发射"
        relation = "now"
        label = f"就在 {fmt_cn(when)}"

    return {
        "when_utc": when.isoformat(),
        "when_cn": fmt_cn(when),
        "noticed_cn": fmt_cn(posted),
        "status": status,
        "relation": relation,
        "source": source,
        "label": label,
    }


def analyze_project(user: dict[str, Any], new_follow: bool, launch: dict[str, Any] | None) -> tuple[int, str]:
    metrics = user.get("public_metrics") or {}
    followers = int(metrics.get("followers_count") or 0)
    created = parse_time(user.get("created_at"))
    bio = user.get("description") or ""
    score = 48
    bits: list[str] = []
    if new_follow:
        score += 16
        bits.append("Solana 新关注")
    else:
        bits.append("在 Solana 关注列表靠前")
    if created:
        age = max(0, (datetime.now(timezone.utc) - created).days)
        bits.append(f"账号 {age} 天")
        if age <= 180:
            score += 8
    if 800 <= followers <= 120_000:
        score += 10
        bits.append(f"粉 {followers:,}（偏新项目区间）")
    elif followers:
        bits.append(f"粉 {followers:,}")
    if any(k in bio.lower() for k in ("tge", "mainnet", "solana", "defi", "nft", "l2", "svm")):
        score += 8
        bits.append("简介像生态项目")
    if launch:
        score += 24
        bits.append(launch.get("status") or "出现发射字眼")
    score = max(0, min(100, score))
    return score, " · ".join(bits) or "待观察"


def diff_new_follows(current: list[str], previous: list[str] | None) -> set[str]:
    cur = [c.lower() for c in current]
    if not previous:
        return set()
    prev = {p.lower() for p in previous}
    return {c for c in cur if c not in prev}


def _headers(bearer: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {bearer}", "User-Agent": "ChainRadar/1.0"}


async def _api_get(bearer: str, path: str, params: dict[str, Any] | None = None) -> tuple[int, dict[str, Any]]:
    async with http_client(timeout=18.0) as c:
        resp = await c.get(f"{TWITTER_API}{path}", headers=_headers(bearer), params=params or {})
        try:
            data = resp.json()
        except Exception:
            data = {"title": resp.text[:180]}
        if not isinstance(data, dict):
            data = {"data": data}
        return resp.status_code, data


def _user_from_api(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "username": (row.get("username") or "").lstrip("@"),
        "name": row.get("name") or row.get("username") or "",
        "description": row.get("description") or "",
        "created_at": row.get("created_at"),
        "url": (row.get("entities") or {}).get("url", {}).get("urls", [{}])[0].get("expanded_url")
        if isinstance((row.get("entities") or {}).get("url"), dict)
        else "",
        "public_metrics": row.get("public_metrics") or {},
        "protected": bool(row.get("protected")),
    }


async def _lookup_solana(bearer: str) -> dict[str, Any] | None:
    code, data = await _api_get(
        bearer,
        "/users/by/username/solana",
        {"user.fields": "description,public_metrics,created_at"},
    )
    if code >= 400:
        return None
    row = data.get("data") or {}
    return _user_from_api(row) if row.get("id") else None


async def fetch_solana_following(bearer: str, limit: int = 40) -> tuple[list[dict[str, Any]], str]:
    sol = await _lookup_solana(bearer)
    if not sol:
        return [], "无法读取 @solana 账号"
    code, data = await _api_get(
        bearer,
        f"/users/{sol['id']}/following",
        {
            "max_results": "100",
            "user.fields": "description,public_metrics,created_at,username,protected,url,entities",
        },
    )
    if code >= 400:
        title = str((data.get("title") or data.get("detail") or code))
        return [], f"关注列表接口 {code}: {title}"
    users = []
    for row in data.get("data") or []:
        u = _user_from_api(row)
        handle = u["username"].lower()
        if not handle or handle in SKIP_HANDLES or u.get("protected") or is_mega_brand(u["name"], handle):
            continue
        users.append(u)
        if len(users) >= limit:
            break
    return users, ""


async def fetch_solana_mentioned_projects(bearer: str, lookback_days: int = 14) -> list[dict[str, Any]]:
    """When the following API is locked, @solana tweets/mentions are the next best 'attention' signal."""
    code, data = await _api_get(
        bearer,
        "/tweets/search/recent",
        {
            "query": "from:solana -is:retweet",
            "max_results": "50",
            "tweet.fields": "created_at,entities",
            "expansions": "entities.mentions.username",
            "user.fields": "description,public_metrics,created_at,username,protected",
        },
    )
    if code >= 400:
        return []
    mentioned: dict[str, dict[str, Any]] = {}
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    users = {u.get("username", "").lower(): _user_from_api(u) for u in (data.get("includes") or {}).get("users", [])}
    for tw in data.get("data") or []:
        created = parse_time(tw.get("created_at"))
        if created and created < cutoff:
            continue
        extra = [m.get("username") for m in ((tw.get("entities") or {}).get("mentions") or [])]
        text = tw.get("text") or ""
        names = extract_mentions(text, extra)
        if not names:
            continue
        welcome = any(h in text.lower() for h in WELCOME_HINTS)
        for name in names:
            cur = mentioned.get(name) or users.get(name) or {"username": name, "name": name, "description": "", "public_metrics": {}}
            cur["username"] = name
            cur.setdefault("name", name)
            cur["_from_mention"] = True
            cur["_welcome"] = bool(welcome or cur.get("_welcome"))
            mentioned[name] = cur
    ranked = sorted(mentioned.values(), key=lambda u: (not u.get("_welcome"), u.get("username")))
    return ranked[:30]


async def nitter_following(handle: str = "solana") -> list[dict[str, Any]]:
    async with http_client(timeout=5.0) as c:
        for base in NITTER_INSTANCES:
            try:
                resp = await c.get(f"{base}/{handle}/following")
                if resp.status_code != 200 or "username" not in resp.text:
                    continue
                users = []
                for m in re.finditer(r'class="username"[^>]*>@([A-Za-z0-9_]{2,15})', resp.text):
                    name = m.group(1)
                    if name.lower() in SKIP_HANDLES:
                        continue
                    users.append({"username": name, "name": name, "description": "", "public_metrics": {}})
                    if len(users) >= 30:
                        break
                if users:
                    return users
            except Exception:
                continue
    return []


async def search_launch_tweets(bearer: str, usernames: list[str]) -> dict[str, dict[str, Any]]:
    found: dict[str, dict[str, Any]] = {}
    if not bearer or not usernames:
        return found
    chunk: list[str] = []
    size = 0
    groups: list[list[str]] = []
    for name in usernames:
        piece = f"from:{name}"
        if size + len(piece) + 4 > 380:
            groups.append(chunk)
            chunk, size = [], 0
        chunk.append(name)
        size += len(piece) + 4
    if chunk:
        groups.append(chunk)
    kw = "(launch OR launching OR launched OR TGE OR 发射 OR 上线 OR presale OR \"now live\" OR \"going live\")"
    for group in groups[:3]:
        q = kw + " (" + " OR ".join(f"from:{n}" for n in group) + ") -is:retweet"
        code, data = await _api_get(
            bearer,
            "/tweets/search/recent",
            {
                "query": q,
                "max_results": "50",
                "tweet.fields": "created_at,author_id",
                "expansions": "author_id",
                "user.fields": "username,name",
            },
        )
        if code >= 400:
            continue
        authors = {u["id"]: u for u in (data.get("includes") or {}).get("users", [])}
        for tw in data.get("data") or []:
            text = tw.get("text") or ""
            if not looks_like_launch_alert(text):
                continue
            author = authors.get(tw.get("author_id") or "", {})
            handle = (author.get("username") or "").lower()
            if not handle:
                continue
            created = parse_time(tw.get("created_at"))
            timing = extract_launch_when(text, created)
            prev = found.get(handle)
            if prev and str(prev.get("created_at") or "") >= str(tw.get("created_at") or ""):
                continue
            found[handle] = {
                "id": tw.get("id"),
                "text": text,
                "created_at": tw.get("created_at"),
                "url": f"https://x.com/{handle}/status/{tw.get('id')}",
                "timing": timing,
            }
    return found


def to_item(
    user: dict[str, Any],
    new_follow: bool,
    launch: dict[str, Any] | None,
    origin: str,
    rank: int = 0,
) -> dict[str, Any]:
    handle = (user.get("username") or "").lstrip("@")
    score, analysis = analyze_project(user, new_follow, launch)
    if rank:
        analysis = f"关注列表第 {rank} 位（越前越新） · {analysis}"
    timing = (launch or {}).get("timing") or {}
    alert = bool(launch)
    kind = "Solana 新关注" if new_follow else ("Solana 最近点名" if origin == "mention" else "Solana 关注列表")
    when_label = timing.get("label") or "暂未提到 launch / 发射"
    status = timing.get("status") or "跟踪中"
    text = (launch or {}).get("text") or (user.get("description") or "Solana 官方账号关注了该项目，持续跟踪发射动态。")
    return {
        "key": f"sol-watch:{handle.lower()}",
        "name": user.get("name") or handle,
        "username": handle,
        "kind": kind,
        "chain": "Solana",
        "text": text,
        "analysis": analysis,
        "launch_status": status if alert else "跟踪中（尚未提到发射）",
        "launch_when": timing.get("when_cn") or "",
        "launch_when_label": when_label,
        "noticed_at": timing.get("noticed_cn") or "",
        "alert": alert,
        "alert_level": "high" if timing.get("relation") in {"upcoming", "now"} else ("mid" if alert else "low"),
        "new_follow": new_follow,
        "watch_kind": "solana_follow",
        "url": (launch or {}).get("url") or twitter_url(handle),
        "twitter": twitter_url(handle),
        "created_at": (launch or {}).get("created_at") or user.get("created_at"),
        "source": "Solana 关注",
        "source_kind": "live",
        "score": score,
        "price_usd": None,
        "followers": int((user.get("public_metrics") or {}).get("followers_count") or 0),
        "extra": {"origin": origin, "bio": user.get("description") or ""},
    }


async def watch_solana_projects(twitter_bearer: str = "", lookback_days: int = 14) -> dict[str, Any]:
    from web3_radar import db

    errors: list[str] = []
    origin = "following"
    users: list[dict[str, Any]] = []
    bearer = (twitter_bearer or "").strip()

    if bearer:
        users, err = await fetch_solana_following(bearer)
        if err:
            errors.append(err)
        if not users:
            mentioned = await fetch_solana_mentioned_projects(bearer, lookback_days)
            if mentioned:
                users = mentioned
                origin = "mention"
                errors.append("关注列表拉不到时，已改用 @solana 最近点名的账号")
    if not users:
        users = await nitter_following("solana")
        if users:
            origin = "nitter"
        elif not bearer:
            errors.append("未配置 Twitter Bearer，无法读取 @solana 最近关注")

    handles = [u.get("username", "").lower() for u in users if u.get("username")]
    prev = await db.cache_get("solana_follow_snapshot") or {}
    prev_handles = list(prev.get("handles") or [])
    new_set = diff_new_follows(handles, prev_handles)
    await db.cache_set("solana_follow_snapshot", {"handles": handles, "origin": origin}, 180 * 86400)

    launches: dict[str, dict[str, Any]] = {}
    if bearer and handles:
        try:
            launches = await search_launch_tweets(bearer, handles)
        except Exception as exc:
            errors.append(f"发射检索: {exc}")

    items = [
        to_item(
            u,
            u.get("username", "").lower() in new_set,
            launches.get((u.get("username") or "").lower()),
            origin,
            rank=i + 1,
        )
        for i, u in enumerate(users)
        if u.get("username")
    ]
    items.sort(key=lambda x: (not x.get("alert"), not x.get("new_follow"), -(x.get("score") or 0)))
    alerts = [x for x in items if x.get("alert")]
    return {
        "items": items,
        "alerts": alerts,
        "follow_count": len(items),
        "new_follow_count": sum(1 for x in items if x.get("new_follow")),
        "alert_count": len(alerts),
        "origin": origin,
        "errors": errors,
    }
