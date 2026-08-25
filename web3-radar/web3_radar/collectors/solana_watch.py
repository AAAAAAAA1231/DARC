from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from web3_radar.collectors.social import (
    is_mega_brand,
    parse_time,
    twitter_url,
)
from web3_radar.http_util import client as http_client

CN = timezone(timedelta(hours=8))
TWITTER_API = "https://api.twitter.com/2"
SOLANA_HANDLE = "solana"
WATCH_PROFILES: dict[str, dict[str, str]] = {
    "solana": {
        "handle": "solana",
        "label": "@solana",
        "tier": "official",
        "chain": "Solana",
        "reason": "Solana 官方",
    },
    "toly": {
        "handle": "toly",
        "label": "@toly",
        "tier": "official",
        "chain": "Solana",
        "reason": "Solana 联合创始人 Toly",
    },
}
SOL_WATCH = ("solana", "toly")
WATCH_ACCOUNTS = SOL_WATCH
WATCH_TOTAL = len(WATCH_ACCOUNTS)
FOLLOW_WINDOW = 300
FOLLOW_LOOKBACK_DAYS = 30
WATCH_GROUPS = {
    "solana": {"chain": "Solana", "accounts": SOL_WATCH, "cache": "solana_follow_snapshot_v4"},
}
FOLLOW_LABEL = {k: v["label"] for k, v in WATCH_PROFILES.items()}
FAMOUS_PROJECT_HANDLES = {
    "jupiterexchange", "jupiter", "orca_so", "orca", "raydiumprotocol", "raydium",
    "phantom", "magiceden", "tensor_hq", "heliuslabs", "helius", "backpack",
    "solflare", "solanamobile", "staratlas", "marinadefinance", "jito_sol",
    "driftprotocol", "kamino", "mangomarkets", "metaplex", "wormhole", "pythnetwork",
    "uniswap", "aaveaave", "opensea", "blur_io", "pancakeswap", "1inch", "sushiswap",
    "compoundfinance", "makerdao", "ensdomains", "lensprotocol", "farcaster_xyz",
    "pumpdotfun", "pumpfun", "dexscreener", "birdeye_so", "gmgnai", "coingecko",
    "coinmarketcap", "messaricrypto", "theblock__", "decryptmedia", "blockworks_",
    "solanalabs", "solanastatus", "solanafndn", "solanafdsn", "binance", "binancezh",
    "okx", "bybit_official", "coinbase", "ethereum", "bitcoin", "base", "arbitrum",
    "optimism", "polygon", "avalancheavax", "bnbchain", "opensea", "blur",
    "dydx", "gmx_io", "lido", "eigenlayer", "ethena", "hyperliquid", "hyperliquidx",
    "aeyakovenko", "rajgokal", "0xmert_", "heyibinance", "superteam",
    "jupiter_exchange", "orcaso", "star_atlas",
}
SKIP_HANDLES = {
    "solana",
    "toly",
    "cz_binance",
} | FAMOUS_PROJECT_HANDLES
MAX_FAME_FOLLOWERS = 120_000
PROJECT_HINTS = (
    "protocol", "network", "layer 1", "layer 2", "layer1", "layer2", "l1 ", "l2 ",
    "svm", "zk", "rollup", "modular", "restaking", "defi", "dex", "perps",
    "mainnet", "testnet", "tge", "token generation", "whitelist", "allowlist",
    "points program", "we're building", "we are building", "our protocol",
    "our network", "on-chain", "onchain", "appchain", "infra",
)
PROJECT_NAME_BITS = ("labs", "protocol", "finance", "network", "chain", "swap", "fi")
PERSON_BIO_HINTS = (
    "opinions are my own", "opinions my own", "views my own", "personal account",
    "tweets are my own", "not the official",
)
TOKEN_LIVE_HINTS = (
    "token is live", "now trading", "trading live", "listed on binance",
    "listed on coinbase", "available on jupiter", "swap on raydium",
    "chart is live", "already live token",
)


def is_famous_web3(name: str, handle: str = "") -> bool:
    h = profile_key(handle or name)
    n = (name or "").strip().lower()
    if h in FAMOUS_PROJECT_HANDLES or h in SKIP_HANDLES:
        return True
    if is_mega_brand(name, h):
        return True
    blob = f"{n} {h}"
    famous_bits = (
        "jupiter", "orca", "raydium", "phantom", "magic eden", "star atlas",
        "pump.fun", "uniswap", "opensea", "coinbase", "binance", "coingecko",
    )
    return any(bit in blob for bit in famous_bits)


def looks_like_project_account(name: str, handle: str, bio: str = "") -> bool:
    blob = f"{name or ''} {handle or ''} {bio or ''}".lower()
    if any(k in blob for k in PROJECT_HINTS):
        return True
    if any(re.search(rf"\b{re.escape(bit)}\b", blob) for bit in PROJECT_NAME_BITS):
        return True
    if re.search(r"\bwe('re| are) (building|launching|shipping)\b", blob):
        return True
    h = profile_key(handle)
    if h.endswith(("labs", "fi", "protocol", "svm", "dex", "app", "xyz")):
        return True
    return False


def looks_like_person(name: str, handle: str, bio: str = "") -> bool:
    h = profile_key(handle)
    n = (name or "").strip()
    b = (bio or "").lower()
    if not h:
        return False
    if looks_like_project_account(n, h, b):
        return False
    if re.match(r"^the(real)?[a-z]{3,}$", h):
        return True
    if re.match(r"^[a-z]+_[a-z]+$", h) and not h.endswith(("_fi", "_so", "_xyz", "_app", "_labs", "_svm")):
        parts = h.split("_")
        if all(p.isalpha() and 3 <= len(p) <= 14 for p in parts):
            return True
    if re.match(r"^[A-Z][a-z]+(?:\s+[A-Z]\.)?(?:\s+[A-Z][a-z]+)+$", n):
        if not re.search(r"\b(labs|protocol|finance|network|chain)\b", n, re.I):
            return True
    if any(x in b for x in PERSON_BIO_HINTS):
        return True
    if re.search(r"\b(i am|i'm)\b.{0,48}\b(founder|co-founder|ceo|cto|investor|trader)\b", b):
        return True
    return False


def keep_unissued_project(user: dict[str, Any]) -> tuple[bool, str]:
    """Only keep unissued Web3 projects — not people, not famous sites."""
    handle = (user.get("username") or "").lstrip("@")
    name = user.get("name") or handle
    bio = user.get("description") or ""
    followers = int((user.get("public_metrics") or {}).get("followers_count") or 0)
    if not handle or handle.lower() in SKIP_HANDLES:
        return False, "skip"
    if is_famous_web3(name, handle):
        return False, "famous"
    if followers >= MAX_FAME_FOLLOWERS:
        return False, "famous"
    if looks_like_person(name, handle, bio):
        return False, "person"
    blob = f"{name} {bio}".lower()
    if any(h in blob for h in TOKEN_LIVE_HINTS):
        return False, "issued"
    if not looks_like_project_account(name, handle, bio):
        if (bio or "").strip():
            return False, "not_project"
    return True, "ok"


async def token_looks_issued(name: str, handle: str) -> bool:
    q = (handle or name or "").strip()
    if not q or len(q) < 3:
        return False
    try:
        async with http_client(timeout=8.0) as c:
            resp = await c.get("https://api.dexscreener.com/latest/dex/search", params={"q": q})
            data = resp.json() if resp.status_code < 400 else {}
    except Exception:
        return False
    pairs = data.get("pairs") if isinstance(data, dict) else None
    if not isinstance(pairs, list):
        return False
    handle_l = profile_key(handle)
    name_l = (name or "").strip().lower()
    for pair in pairs[:8]:
        if not isinstance(pair, dict):
            continue
        blob = str(pair).lower()
        if handle_l not in blob and name_l not in blob:
            continue
        liq = float(((pair.get("liquidity") or {}) if isinstance(pair.get("liquidity"), dict) else {}).get("usd") or 0)
        if liq >= 500_000:
            return True
    return False

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


def profile_key(name: str) -> str:
    return str(name or "").lower().lstrip("@")


def watch_handle(account: str) -> str:
    key = profile_key(account)
    return str((WATCH_PROFILES.get(key) or {}).get("handle") or account)


def account_tier(name: str) -> str:
    return str((WATCH_PROFILES.get(profile_key(name)) or {}).get("tier") or "")


def account_reason(name: str) -> str:
    return str((WATCH_PROFILES.get(profile_key(name)) or {}).get("reason") or "")


def verified_followers(followed_by: list[str] | None) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in followed_by or []:
        n = profile_key(raw)
        if n not in WATCH_PROFILES or n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out


def official_followers(followed_by: list[str] | None) -> list[str]:
    return [n for n in verified_followers(followed_by) if account_tier(n) == "official"]


def industry_followers(followed_by: list[str] | None) -> list[str]:
    return [n for n in verified_followers(followed_by) if account_tier(n) == "industry"]


def official_follow_total(followed_by: list[str] | None) -> int:
    names = set(official_followers(followed_by))
    if names & set(SOL_WATCH):
        return len(SOL_WATCH)
    return len(names)


def chain_for_follows(followed_by: list[str] | None, default: str = "Solana") -> str:
    names = verified_followers(followed_by)
    bits: list[str] = []
    for n in names:
        chain = str((WATCH_PROFILES.get(n) or {}).get("chain") or "")
        if chain and chain not in bits:
            bits.append(chain)
    return " + ".join(bits) or default


def follow_reason_bits(followed_by: list[str] | None) -> list[str]:
    bits: list[str] = []
    for n in verified_followers(followed_by):
        label = FOLLOW_LABEL.get(n, "@" + n)
        reason = account_reason(n)
        if account_tier(n) == "industry" and reason:
            bits.append(f"{label} 正在关注（{reason}）")
        else:
            bits.append(f"{label} 正在关注")
    return bits


def follow_badge_text(followed_by: list[str] | None) -> str:
    names = verified_followers(followed_by)
    if not names:
        return ""
    official = official_followers(names)
    bits = follow_reason_bits(names)
    if official:
        total = official_follow_total(official)
        head = f"官方关注 {len(official)}/{total}"
        return head + " · " + "、".join(bits)
    return ""


def follow_count_label(followed_by: list[str] | None) -> str:
    official = official_followers(followed_by)
    if official:
        total = official_follow_total(official)
        return f"官方关注 {len(official)}/{total}"
    return ""


def follow_tier_of(followed_by: list[str] | None) -> str:
    if official_followers(followed_by):
        return "official"
    if industry_followers(followed_by):
        return "industry"
    return ""


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


async def _lookup_user(bearer: str, username: str) -> dict[str, Any] | None:
    code, data = await _api_get(
        bearer,
        f"/users/by/username/{username}",
        {"user.fields": "description,public_metrics,created_at"},
    )
    if code >= 400:
        return None
    row = data.get("data") or {}
    return _user_from_api(row) if row.get("id") else None


async def fetch_account_following(
    bearer: str, username: str, limit: int = 80
) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    """Newest follows first. Only scan FOLLOW_WINDOW rows (~last month)."""
    owner = await _lookup_user(bearer, username)
    stats = {
        "account": username,
        "following_total": int((owner or {}).get("public_metrics", {}).get("following_count") or 0) if owner else 0,
        "fetched": 0,
        "kept": 0,
        "window": FOLLOW_WINDOW,
    }
    if not owner:
        return [], f"无法读取 @{username}", stats
    users: list[dict[str, Any]] = []
    token = None
    scanned = 0
    while scanned < FOLLOW_WINDOW:
        params: dict[str, Any] = {
            "max_results": "100",
            "user.fields": "description,public_metrics,created_at,username,protected,url,entities",
        }
        if token:
            params["pagination_token"] = token
        code, data = await _api_get(bearer, f"/users/{owner['id']}/following", params)
        if code >= 400:
            title = str((data.get("title") or data.get("detail") or code))
            if users:
                break
            return [], f"@{username} 关注列表 {code}: {title}", stats
        rows = data.get("data") or []
        if not rows:
            break
        for row in rows:
            if scanned >= FOLLOW_WINDOW:
                break
            scanned += 1
            stats["fetched"] = scanned
            u = _user_from_api(row)
            handle = u["username"].lower()
            if not handle or handle in SKIP_HANDLES or u.get("protected") or is_mega_brand(u["name"], handle):
                continue
            if not keep_unissued_project(u)[0]:
                continue
            users.append(u)
            if len(users) >= limit:
                break
        token = (data.get("meta") or {}).get("next_token")
        if not token or scanned >= FOLLOW_WINDOW or len(users) >= limit:
            break
    stats["kept"] = len(users)
    return users, "", stats


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
            if not keep_unissued_project(cur)[0]:
                continue
            cur["_from_mention"] = True
            cur["_welcome"] = bool(welcome or cur.get("_welcome"))
            mentioned[name] = cur
    ranked = sorted(mentioned.values(), key=lambda u: (not u.get("_welcome"), u.get("username")))
    return ranked[:30]


FOLLOW_CARD = re.compile(
    r'\[@([A-Za-z0-9_]{2,15})\]\([^)]+\s+"@\1"\)',
    re.I,
)
FOLLOW_HTML = re.compile(
    r'class="username"[^>]*title="@([A-Za-z0-9_]{2,15})"',
    re.I,
)
FOLLOW_PAGE_BAD = (
    "anubis",
    "not a bot",
    "verifying your browser",
    "just a moment",
    "abusealleviation",
)
PUBLIC_FOLLOW_URLS = (
    "https://r.jina.ai/https://nitter.tiekoetter.com/{handle}/following",
    "https://r.jina.ai/https://nitter.poast.org/{handle}/following",
    "https://nitter.tiekoetter.com/{handle}/following",
    "https://nitter.poast.org/{handle}/following",
)


def parse_public_following(text: str, owner: str) -> list[dict[str, Any]]:
    """Only accept a page that is clearly that account's following list."""
    raw = text or ""
    low = raw.lower()
    owner = owner.lower().lstrip("@")
    if any(bit in low for bit in FOLLOW_PAGE_BAD):
        return []
    titled = f"people followed by @{owner}" in low or f"people followed by {owner}" in low
    html_list = f"/{owner}/following" in low and ("timeline-item" in low or 'class="username"' in low)
    if not titled and not html_list:
        return []
    handles: list[str] = []
    for rx in (FOLLOW_CARD, FOLLOW_HTML):
        for m in rx.finditer(raw):
            name = m.group(1).lower()
            if name == owner or name in handles:
                continue
            dummy = {"username": name, "name": name, "description": "", "public_metrics": {}}
            if not keep_unissued_project(dummy)[0]:
                continue
            handles.append(name)
        if handles:
            break
    if len(handles) < 5:
        return []
    return [{"username": h, "name": h, "description": "", "public_metrics": {}} for h in handles[:80]]


async def fetch_public_following(handle: str) -> tuple[list[dict[str, Any]], str, dict[str, Any]]:
    stats = {"account": handle, "following_total": 0, "fetched": 0, "kept": 0, "origin": "public"}
    async with http_client(timeout=18.0) as c:
        for url in PUBLIC_FOLLOW_URLS:
            try:
                resp = await c.get(url.format(handle=handle))
            except Exception:
                continue
            users = parse_public_following(resp.text or "", handle)
            if not users:
                continue
            stats["fetched"] = len(users)
            stats["kept"] = len(users)
            m = re.search(r"Following\s+([\d,]+)", resp.text or "", re.I)
            if m:
                stats["following_total"] = int(m.group(1).replace(",", ""))
            return users, "", stats
    return [], f"公开关注页读不到 @{handle}", stats


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
    followed_by: list[str] | None = None,
) -> dict[str, Any] | None:
    handle = (user.get("username") or "").lstrip("@")
    if not keep_unissued_project(user)[0]:
        return None
    verified = verified_followers(followed_by or user.get("followed_by"))
    if not verified:
        return None
    proof = follow_badge_text(verified)
    score, analysis = analyze_project(user, new_follow, launch)
    analysis = proof + (" · " + analysis if analysis else "")
    if rank:
        analysis = f"关注列表第 {rank} 位（越前越新） · {analysis}"
    timing = (launch or {}).get("timing") or {}
    alert = bool(launch)
    labels = " / ".join(FOLLOW_LABEL.get(n, "@" + n) for n in verified)
    chain = chain_for_follows(verified, default="Solana")
    official = official_followers(verified)
    industry = industry_followers(verified)
    total = official_follow_total(official)
    tier = follow_tier_of(verified)
    kind = f"{labels} 最近关注"
    when_label = timing.get("label") or "暂未提到 launch / 发射"
    status = timing.get("status") or "跟踪中"
    followers = int((user.get("public_metrics") or {}).get("followers_count") or 0)
    text = (launch or {}).get("text") or (user.get("description") or f"{proof}，持续跟踪发射动态。")
    reasons = [{"handle": n, "label": FOLLOW_LABEL.get(n, "@" + n), "tier": account_tier(n), "reason": account_reason(n)} for n in verified]
    return {
        "key": f"sol-watch:{handle.lower()}",
        "name": user.get("name") or handle,
        "username": handle,
        "kind": kind,
        "chain": chain,
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
        "followed_by": verified,
        "official_follow_count": len(official),
        "official_follow_total": total,
        "industry_follow_count": len(industry),
        "follow_tier": tier,
        "follow_reasons": reasons,
        "follow_reason": "；".join(account_reason(n) for n in industry if account_reason(n)),
        "follow_proof": proof,
        "follow_count_label": follow_count_label(verified),
        "verified_follow": True,
        "token_status": "未发币",
        "url": (launch or {}).get("url") or twitter_url(handle),
        "twitter": twitter_url(handle),
        "created_at": (launch or {}).get("created_at") or user.get("created_at"),
        "source": "已核实关注",
        "source_kind": "live",
        "score": score,
        "price_usd": None,
        "followers": followers,
        "extra": {"origin": origin, "bio": user.get("description") or "", "followed_by": verified},
    }


async def watch_solana_projects(
    twitter_bearer: str = "",
    lookback_days: int = FOLLOW_LOOKBACK_DAYS,
    group: str = "solana",
) -> dict[str, Any]:
    from web3_radar import db

    cfg = WATCH_GROUPS.get(group) or WATCH_GROUPS["solana"]
    accounts = tuple(cfg["accounts"])
    chain = str(cfg["chain"])
    errors: list[str] = []
    origin = "following"
    bearer = (twitter_bearer or "").strip()
    merged: dict[str, dict[str, Any]] = {}
    scan_stats: list[dict[str, Any]] = []

    async def _merge(account: str, users: list[dict[str, Any]]) -> None:
        for u in users:
            name = (u.get("username") or "").lower()
            if not name:
                continue
            rec = merged.get(name)
            if rec is None:
                rec = dict(u)
                rec["followed_by"] = []
                merged[name] = rec
            if account not in rec["followed_by"]:
                rec["followed_by"].append(account)

    if bearer:
        for account in accounts:
            users, err, stats = await fetch_account_following(bearer, watch_handle(account), limit=100)
            scan_stats.append(stats)
            if err:
                errors.append(err)
                continue
            await _merge(account, users)
    if not merged:
        origin = "public_following"
        for account in accounts:
            users, err, stats = await fetch_public_following(watch_handle(account))
            scan_stats.append(stats)
            if err:
                errors.append(err)
                continue
            await _merge(account, users)

    users = [u for u in merged.values() if verified_followers(u.get("followed_by"))]
    users = [u for u in users if keep_unissued_project(u)[0]]
    if users:
        sem = asyncio.Semaphore(4)

        async def _keep(u: dict[str, Any]) -> dict[str, Any] | None:
            async with sem:
                if await token_looks_issued(str(u.get("name") or ""), str(u.get("username") or "")):
                    return None
                return u

        checked = await asyncio.gather(*[_keep(u) for u in users[:40]])
        users = [u for u in checked if u] + [u for u in users[40:] if keep_unissued_project(u)[0]]
    if not users:
        errors.append("没有从关注列表核实到项目，宁可不显示，避免把观察池/其它项目混进来")
        return {
            "items": [],
            "alerts": [],
            "follow_count": 0,
            "new_follow_count": 0,
            "alert_count": 0,
            "origin": origin,
            "scan_stats": scan_stats,
            "errors": errors,
        }

    handles = [u.get("username", "").lower() for u in users if u.get("username")]
    prev = await db.cache_get(str(cfg["cache"])) or {}
    prev_handles = list(prev.get("handles") or [])
    new_set = diff_new_follows(handles, prev_handles)
    await db.cache_set(str(cfg["cache"]), {"handles": handles, "origin": origin, "chain": chain}, 180 * 86400)

    launches: dict[str, dict[str, Any]] = {}
    if bearer and handles:
        try:
            launches = await search_launch_tweets(bearer, handles)
        except Exception as exc:
            errors.append(f"发射检索: {exc}")

    items: list[dict[str, Any]] = []
    for i, u in enumerate(users):
        row = to_item(
            u,
            u.get("username", "").lower() in new_set,
            launches.get((u.get("username") or "").lower()),
            origin,
            rank=i + 1,
            followed_by=u.get("followed_by"),
        )
        if row:
            items.append(row)
    items.sort(
        key=lambda x: (
            0 if x.get("follow_tier") == "official" else 1,
            -(x.get("official_follow_count") or 0),
            -(x.get("industry_follow_count") or 0),
            not x.get("alert"),
            not x.get("new_follow"),
            -(x.get("score") or 0),
        )
    )
    alerts = [x for x in items if x.get("alert")]
    return {
        "items": items,
        "alerts": alerts,
        "follow_count": len(items),
        "new_follow_count": sum(1 for x in items if x.get("new_follow")),
        "alert_count": len(alerts),
        "origin": origin,
        "scan_stats": scan_stats,
        "errors": errors,
    }
