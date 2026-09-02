"""Hunt new-project / presale posts on X (Twitter) over a 30-day window."""

from __future__ import annotations

import asyncio
import html
import logging
import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, quote_plus, unquote, urlparse

import httpx

from web3_radar.config import load_settings
from web3_radar.collectors.social import nitter_search, parse_time, twitter_recent_search
from web3_radar.engine.launch_rank import rank_launch_items, within_lookback
from web3_radar.http_util import DEFAULT_HEADERS

log = logging.getLogger(__name__)

HUNT_QUERIES = (
    "发射 新项目",
    "预售 代币",
    "预售 crypto",
    "新平台 web3",
    "新项目 预售",
    "token launch",
    "crypto presale",
    "fair launch crypto",
    "IDO presale",
    "newproject crypto",
    "打新 预售",
)

RSSHUB_HOSTS = (
    "https://rsshub.app",
    "https://rsshub.rssforever.com",
    "https://rsshub.rss.tips",
)

NITTER_RSS_HOSTS = (
    "https://nitter.tiekoetter.com",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
)

_TWEET_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([^/\s\"'<>]+)/status/(\d+)",
    re.I,
)
_PROFILE_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:twitter\.com|x\.com)/([^/\s\"'<>#?]+)/?(?:\?.*)?$",
    re.I,
)
_STATUS_ID_RE = re.compile(r"/status/(\d+)")
_RESERVED_PATHS = {"home", "search", "i", "intent", "explore", "settings", "compose", "messages", "hashtag", "share"}
_HANDLE_RE = re.compile(r"@([A-Za-z0-9_]{2,30})")
_ITEM_RE = re.compile(r"<item>(.*?)</item>", re.I | re.S)
_TITLE_RE = re.compile(r"<title>(.*?)</title>", re.I | re.S)
_LINK_RE = re.compile(r"<link>(.*?)</link>", re.I | re.S)
_DATE_RE = re.compile(r"<pubDate>(.*?)</pubDate>", re.I | re.S)
_DESC_RE = re.compile(r"<description>(.*?)</description>", re.I | re.S)
_DDG_HREF_RE = re.compile(r"uddg=([^&\"]+)")
_DDG_A_RE = re.compile(
    r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_LITE_A_RE = re.compile(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.I | re.S)
_BING_A_RE = re.compile(
    r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>',
    re.I | re.S,
)
_TAG_RE = re.compile(r"<[^>]+>")


async def hunt_launches(lookback_days: int = 30) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since = now - timedelta(days=lookback_days)
    settings = load_settings()
    bearer = str(settings.get("twitter_bearer_token") or "").strip()
    raw: list[dict[str, Any]] = []
    sources_used: list[str] = []
    errors: list[str] = []

    async with httpx.AsyncClient(
        timeout=10.0,
        follow_redirects=True,
        headers={**DEFAULT_HEADERS, "User-Agent": "Mozilla/5.0 GongZuoTaiLaunchHunt/1.0"},
    ) as client:
        batches = await asyncio.gather(
            _from_twitter_api(bearer),
            _from_nitter_html(),
            _from_rsshub(client),
            _from_nitter_rss(client, lookback_days),
            _from_duckduckgo(client, since),
            _from_bing(client, since),
            return_exceptions=True,
        )

    labels = ("twitter-api", "nitter", "rsshub", "nitter-rss", "duckduckgo", "bing")
    for label, batch in zip(labels, batches, strict=True):
        if isinstance(batch, Exception):
            errors.append(f"{label}: {batch}")
            continue
        rows, note = batch
        if note:
            errors.append(note)
        if rows:
            raw.extend(rows)
            sources_used.append(label)

    merged = _dedupe(raw)
    windowed: list[dict[str, Any]] = []
    for item in merged:
        created = item.get("created_at")
        if isinstance(created, str):
            created = parse_time(created)
            item["created_at"] = created
        if not within_lookback(created if isinstance(created, datetime) else None, now, lookback_days):
            continue
        windowed.append(item)

    ranked = rank_launch_items(windowed, now=now, lookback_days=lookback_days)
    payload = []
    for i, row in enumerate(ranked[:80], start=1):
        created = row.get("created_at")
        payload.append(
            {
                "rank": i,
                "id": row.get("id") or "",
                "handle": row.get("handle") or "",
                "text": (row.get("text") or "")[:500],
                "url": row.get("url") or "",
                "created_at": created.isoformat() if isinstance(created, datetime) else (created or ""),
                "score": int(row.get("score") or 0),
                "institutions": row.get("institutions") or [],
                "notable": row.get("notable"),
                "reasons": row.get("reasons") or [],
                "metrics": row.get("metrics") or {},
                "source": row.get("source") or "twitter",
            }
        )
    return {
        "ok": True,
        "scanned_at": now.isoformat(),
        "lookback_days": lookback_days,
        "since": since.date().isoformat(),
        "sources": sources_used,
        "errors": errors[:10],
        "queries": list(HUNT_QUERIES),
        "total_raw": len(merged),
        "count": len(payload),
        "items": payload,
        "disclaimer": "推特检索信号，按机构/名人/VC 关注排序。不是投资建议，提及可能是转发或传闻。",
    }


async def _from_twitter_api(bearer: str) -> tuple[list[dict[str, Any]], str]:
    if not bearer:
        return [], ""
    posts: list[dict[str, Any]] = []
    errors: list[str] = []
    results = await asyncio.gather(
        *[twitter_recent_search(bearer, query, max_results=40) for query in HUNT_QUERIES[:6]],
        return_exceptions=True,
    )
    for batch in results:
        if isinstance(batch, Exception):
            errors.append(str(batch))
            continue
        for tw in batch:
            posts.append(_normalize_social(tw, source="twitter-api"))
    return posts, (f"twitter-api: {errors[0]}" if errors and not posts else "")


async def _from_nitter_html() -> tuple[list[dict[str, Any]], str]:
    posts: list[dict[str, Any]] = []
    for query in HUNT_QUERIES[:4]:
        try:
            tweets = await nitter_search(query)
        except Exception:
            continue
        for tw in tweets:
            posts.append(_normalize_social(tw, source="nitter"))
        if posts:
            break
    return posts, ""


async def _from_rsshub(client: httpx.AsyncClient) -> tuple[list[dict[str, Any]], str]:
    items: list[dict[str, Any]] = []
    for host in RSSHUB_HOSTS:
        got_any = False
        for query in HUNT_QUERIES[:5]:
            for path in (f"/twitter/search/{quote(query)}", f"/twitter/keyword/{quote(query)}"):
                xml = await _get_text(client, host + path)
                if not xml or "<item>" not in xml.lower():
                    continue
                got_any = True
                items.extend(parse_rss(xml, source="rsshub"))
                break
        if got_any:
            break
    return items, ""


async def _from_nitter_rss(client: httpx.AsyncClient, lookback_days: int) -> tuple[list[dict[str, Any]], str]:
    items: list[dict[str, Any]] = []
    since = (datetime.now(timezone.utc) - timedelta(days=lookback_days)).date().isoformat()
    for host in NITTER_RSS_HOSTS:
        got_any = False
        for query in HUNT_QUERIES[:4]:
            q = quote_plus(f"{query} since:{since}")
            xml = await _get_text(client, f"{host}/search/rss?f=tweets&q={q}")
            if not xml or "<item>" not in xml.lower():
                continue
            got_any = True
            items.extend(parse_rss(xml, source="nitter-rss"))
        if got_any:
            break
    return items, ""


async def _from_duckduckgo(client: httpx.AsyncClient, since: datetime) -> tuple[list[dict[str, Any]], str]:
    async def one(query: str) -> list[dict[str, Any]]:
        q = f"{query} (site:x.com OR site:twitter.com)"
        items: list[dict[str, Any]] = []
        html_text = await _get_text(client, "https://html.duckduckgo.com/html/?q=" + quote_plus(q))
        if html_text:
            items.extend(parse_duckduckgo(html_text))
        if not html_text or "result__a" not in html_text:
            lite = await _get_text(client, "https://lite.duckduckgo.com/lite/?q=" + quote_plus(q))
            if lite:
                items.extend(parse_ddg_lite(lite))
        return items

    batches = await asyncio.gather(*[one(q) for q in HUNT_QUERIES], return_exceptions=True)
    items: list[dict[str, Any]] = []
    for batch in batches:
        if isinstance(batch, Exception):
            continue
        items.extend(batch)
    return items, ""


async def _from_bing(client: httpx.AsyncClient, since: datetime) -> tuple[list[dict[str, Any]], str]:
    async def one(query: str) -> list[dict[str, Any]]:
        q = f"{query} site:x.com"
        page = await _get_text(client, "https://www.bing.com/search?q=" + quote_plus(q) + "&count=20")
        return parse_bing(page) if page else []

    batches = await asyncio.gather(*[one(q) for q in HUNT_QUERIES[:6]], return_exceptions=True)
    items: list[dict[str, Any]] = []
    for batch in batches:
        if isinstance(batch, Exception):
            continue
        items.extend(batch)
    return items, ""


async def _get_text(client: httpx.AsyncClient, url: str) -> str:
    try:
        resp = await client.get(url)
        if resp.status_code >= 400:
            return ""
        return resp.text or ""
    except Exception as exc:  # noqa: BLE001
        log.info("fetch %s failed: %s", url, exc)
        return ""


def parse_rss(xml: str, source: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for block in _ITEM_RE.findall(xml):
        title = _strip(_first(_TITLE_RE, block))
        link = _strip(_first(_LINK_RE, block))
        desc = _strip(_first(_DESC_RE, block))
        pub = _strip(_first(_DATE_RE, block))
        text = title or desc
        url = unwrap_nitter(link)
        handle, tweet_id = handle_id_from_url(url)
        if not handle:
            m = _HANDLE_RE.search(text)
            handle = m.group(1) if m else ""
        created = parse_pub_date(pub)
        out.append(
            {
                "id": tweet_id or url or title[:40],
                "handle": handle,
                "text": text or desc,
                "url": url,
                "created_at": created,
                "metrics": {},
                "source": source,
            }
        )
    return out


def parse_duckduckgo(page: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for href, title_html in _DDG_A_RE.findall(page):
        url = unwrap_ddg(html.unescape(href))
        row = _from_search_hit(url, _strip(title_html), source="duckduckgo")
        if row:
            out.append(row)
    return out


def parse_ddg_lite(page: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for href, title_html in _LITE_A_RE.findall(page):
        url = unwrap_ddg(html.unescape(href))
        row = _from_search_hit(url, _strip(title_html), source="duckduckgo")
        if row:
            out.append(row)
    return out


def parse_bing(page: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for href, title_html in _BING_A_RE.findall(page):
        url = html.unescape(href)
        row = _from_search_hit(url, _strip(title_html), source="bing")
        if row:
            out.append(row)
    return out


def _from_search_hit(url: str, title: str, source: str) -> dict[str, Any] | None:
    handle, tweet_id = handle_id_from_url(url)
    if not handle:
        handle = handle_from_profile(url)
    if not handle:
        return None
    return {
        "id": tweet_id or f"profile:{handle}:{title[:40]}",
        "handle": handle,
        "text": title,
        "url": canonicalize_tweet_url(url, handle, tweet_id),
        "created_at": None,
        "metrics": {},
        "source": source,
    }


def unwrap_ddg(href: str) -> str:
    m = _DDG_HREF_RE.search(href)
    if m:
        return unquote(m.group(1))
    if href.startswith("//"):
        return "https:" + href
    return href


def unwrap_nitter(url: str) -> str:
    u = (url or "").strip()
    parsed = urlparse(u)
    if "nitter" in parsed.netloc.lower():
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) >= 3 and parts[1] == "status":
            return f"https://x.com/{parts[0]}/status/{parts[2]}"
    return u


def handle_id_from_url(url: str) -> tuple[str, str]:
    m = _TWEET_URL_RE.search(url or "")
    if m:
        return m.group(1), m.group(2)
    m2 = _STATUS_ID_RE.search(url or "")
    return "", m2.group(1) if m2 else ""


def handle_from_profile(url: str) -> str:
    cleaned = (url or "").split("?")[0].rstrip("/")
    if "/status/" in cleaned.lower():
        return ""
    m = _PROFILE_URL_RE.search(cleaned)
    if not m:
        return ""
    handle = m.group(1)
    if handle.lower() in _RESERVED_PATHS:
        return ""
    return handle


def is_tweet_url(url: str) -> bool:
    return bool(_TWEET_URL_RE.search(url or "")) or bool(handle_from_profile(url))


def canonicalize_tweet_url(url: str, handle: str, tweet_id: str) -> str:
    if handle and tweet_id:
        return f"https://x.com/{handle}/status/{tweet_id}"
    if handle:
        return f"https://x.com/{handle}"
    return url


def _normalize_social(tw: dict[str, Any], source: str) -> dict[str, Any]:
    created = parse_time(tw.get("created_at") or tw.get("_created"))
    handle = str(tw.get("username") or tw.get("handle") or "")
    return {
        "id": tw.get("id") or "",
        "handle": handle,
        "text": tw.get("text") or "",
        "url": tw.get("url") or "",
        "created_at": created,
        "metrics": tw.get("metrics") or {},
        "source": source,
    }


def _dedupe(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for item in items:
        key = str(item.get("id") or "") or (str(item.get("url") or "") + str(item.get("text") or "")[:80])
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _first(regex: re.Pattern[str], text: str) -> str:
    m = regex.search(text or "")
    return m.group(1) if m else ""


def _strip(text: str) -> str:
    raw = html.unescape(text or "")
    raw = _TAG_RE.sub(" ", raw)
    return re.sub(r"\s+", " ", raw).strip()


def parse_pub_date(value: str) -> datetime | None:
    raw = (value or "").strip()
    if not raw:
        return None
    parsed = parse_time(raw)
    if parsed:
        return parsed
    try:
        dt = parsedate_to_datetime(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (TypeError, ValueError, IndexError):
        return None
