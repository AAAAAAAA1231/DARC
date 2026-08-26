from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from web3_radar.collectors.social import is_mega_brand, twitter_url
from web3_radar.collectors.ecosystem import is_solana
from web3_radar.http_util import client as http_client
from web3_radar.http_util import get_json

LLAMA_PROTOCOLS = "https://api.llama.fi/protocols"
CRYPTORANK_COINS = "https://api.cryptorank.io/v0/coins"
WEB3_CAREER_AMB = "https://web3.career/ambassador-jobs"


def _iso_from_unix(ts: Any) -> str | None:
    try:
        n = float(ts)
        if n > 10_000_000_000:
            n = n / 1000
        return datetime.fromtimestamp(n, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return None


async def fetch_new_protocols(lookback_days: int = 45, limit: int = 40, solana_only: bool = True) -> list[dict[str, Any]]:
    """Recently listed DeFi/web3 protocols — new projects, not CEX listings."""
    rows = await get_json(LLAMA_PROTOCOLS, timeout=20.0)
    if not isinstance(rows, list):
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    items: list[dict[str, Any]] = []
    for p in rows:
        listed = p.get("listedAt")
        created = _iso_from_unix(listed)
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created)
        except ValueError:
            continue
        if dt < cutoff:
            continue
        name = (p.get("name") or "").strip()
        if not name or is_mega_brand(name):
            continue
        handle = (p.get("twitter") or "").strip().lstrip("@")
        url = (p.get("url") or "").strip()
        if not handle and not url:
            continue
        chains = p.get("chains") or []
        if solana_only and not is_solana(name, p.get("description"), p.get("category"), chains=chains):
            continue
        desc = (p.get("description") or p.get("category") or "新上线的 Web3 项目")
        tw = twitter_url(handle)
        items.append(
            {
                "key": f"llama:{p.get('slug') or p.get('id') or name}",
                "name": name,
                "kind": "Sol 新项目上线",
                "chain": "Solana",
                "text": f"{desc} · 分类 {p.get('category') or '-'} · TVL ${float(p.get('tvl') or 0):,.0f} · 链 {', '.join(str(c) for c in chains[:4]) or '-'}",
                "url": url or tw,
                "twitter": tw,
                "created_at": created,
                "source": "新协议",
                "source_kind": "live",
                "price_usd": None,
                "extra": {"category": p.get("category"), "tvl": p.get("tvl"), "twitter": handle, "chains": chains},
            }
        )
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items[:limit]


async def fetch_pre_tge_projects(limit: int = 24, solana_only: bool = True) -> list[dict[str, Any]]:
    """Unissued / funding-stage projects that may open whitelist, testnet, or TGE."""
    payload = await get_json(CRYPTORANK_COINS, params={"lifeCycle": "funding", "limit": 80}, timeout=20.0)
    rows = payload.get("data") if isinstance(payload, dict) else payload
    items: list[dict[str, Any]] = []
    for c in rows or []:
        name = (c.get("name") or "").strip()
        key = c.get("key") or name
        if not name or is_mega_brand(name):
            continue
        cat = c.get("category")
        if isinstance(cat, dict):
            cat = cat.get("name")
        platforms = c.get("platforms") or c.get("coreEcosystems") or []
        if solana_only and not is_solana(name, cat, c.get("symbol"), chains=platforms):
            continue
        kind = "Sol 预 TGE / 未发币项目"
        if (c.get("type") or "") == "token":
            kind = "Sol 预 TGE 新代币项目"
        url = f"https://cryptorank.io/price/{key}"
        items.append(
            {
                "key": f"cr:{key}",
                "name": name,
                "kind": kind,
                "chain": "Solana",
                "text": f"尚未进入交易阶段，适合跟官网/X 上的白名单、测试网、TGE 窗口。类型 {c.get('type') or '-'} · {cat or ''}",
                "url": url,
                "twitter": "",
                "created_at": c.get("listingDate"),
                "source": "预TGE",
                "source_kind": "live",
                "price_usd": None,
                "extra": {"lifeCycle": c.get("lifeCycle"), "type": c.get("type"), "category": cat},
            }
        )
        if len(items) >= limit:
            break
    return items


async def fetch_ambassador_jobs() -> list[dict[str, Any]]:
    """Ambassador roles posted by projects (Web3.career), filtered away from mega CEX brands."""
    async with http_client(timeout=18.0) as c:
        resp = await c.get(WEB3_CAREER_AMB)
        resp.raise_for_status()
        html = resp.text
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.S):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            continue
        if data.get("@type") != "JobPosting":
            continue
        title = str(data.get("title") or "").strip()
        if "ambassador" not in title.lower() and "大使" not in title:
            continue
        org = ((data.get("hiringOrganization") or {}).get("name") or "").strip() or "未知项目"
        if is_mega_brand(org) or is_mega_brand(title):
            continue
        if any(k in title.lower() for k in ("manager", "intern", "internship")):
            continue
        key = f"career:{org.lower()}:{title.lower()[:40]}"
        if key in seen:
            continue
        seen.add(key)
        desc = re.sub("<[^>]+>", " ", str(data.get("description") or ""))
        desc = re.sub(r"\s+", " ", desc).strip()[:280]
        url = data.get("url") or WEB3_CAREER_AMB
        items.append(
            {
                "key": key,
                "project": org,
                "username": "",
                "title": title,
                "text": desc or title,
                "url": url,
                "twitter": "",
                "created_at": str(data.get("datePosted") or ""),
                "deadline": str(data.get("validThrough") or "以岗位页为准"),
                "priority": "中",
                "priority_detail": "中 · 项目方招聘大使",
                "score": 72,
                "source": "web3.career",
                "source_kind": "live",
            }
        )
    return items[:30]
