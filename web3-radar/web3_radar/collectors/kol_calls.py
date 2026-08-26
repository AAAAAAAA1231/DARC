from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from web3_radar.collectors.social import nitter_search, parse_time, twitter_recent_search, twitter_url
from web3_radar.http_util import get_json

DEXSCREENER_TOKEN = "https://api.dexscreener.com/latest/dex/tokens/"
KOL_MAX_AGE = timedelta(hours=24)

# Real, launch/meme-relevant callers. Do not invent tweets or CAs.
KOL_WATCH = [
    {
        "handle": "blknoiz06",
        "name": "Ansem",
        "reason": "Solana 生态知名交易员，常转发新币合约地址",
    },
    {
        "handle": "MustStopMurad",
        "name": "Murad",
        "reason": "Meme 叙事意见领袖，喊单影响力大",
    },
    {
        "handle": "HsakaTrades",
        "name": "Hsaka",
        "reason": "加密交易员，常点评新币与合约",
    },
    {
        "handle": "DegenSpartan",
        "name": "DegenSpartan",
        "reason": "加密圈老牌 KOL，常讨论高波动币种",
    },
    {
        "handle": "Cupseyy",
        "name": "Cupsey",
        "reason": "Solana 新币交易员，推文常带 CA",
    },
    {
        "handle": "SolBigBrain",
        "name": "SolBigBrain",
        "reason": "Solana 链上交易员，跟踪新池与 CA",
    },
]

EVM_CA = re.compile(r"0x[a-fA-F0-9]{40}")
SOL_CA = re.compile(r"\b[1-9A-HJ-NP-Za-km-z]{32,44}\b")
_SOL_FALSE = {
    "abcdefghijklmnopqrstuvwxyz123456789",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def extract_cas(text: str) -> list[tuple[str, str]]:
    """Return (address, guessed_chain_id) pairs from a tweet. chain_id may be refined later."""
    blob = text or ""
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for addr in EVM_CA.findall(blob):
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((addr, "evm"))
    for addr in SOL_CA.findall(blob):
        if addr.lower().startswith("0x"):
            continue
        if addr.lower() in _SOL_FALSE:
            continue
        if not re.search(r"\d", addr) or not re.search(r"[A-Za-z]", addr):
            continue
        letters = re.sub(r"[^A-Za-z]", "", addr)
        if letters.isupper() or letters.islower():
            # Real Solana keys mix case; all-one-case strings are usually words.
            if len(addr) < 40:
                continue
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append((addr, "solana"))
    return out


def _kol_by_handle() -> dict[str, dict[str, str]]:
    return {str(k["handle"]).lower(): k for k in KOL_WATCH}


def tweet_is_fresh(created: Any, now: datetime | None = None) -> bool:
    now = now or _now()
    dt = parse_time(created)
    if not dt:
        return True
    return dt >= now - KOL_MAX_AGE


async def _resolve_token(address: str, guessed: str) -> dict[str, Any] | None:
    from web3_radar.collectors.meme import CHAIN_LABEL, _num, _pair_to_item

    try:
        payload = await get_json(DEXSCREENER_TOKEN + address, timeout=8.0)
    except Exception:
        payload = None
    pairs = (payload or {}).get("pairs") if isinstance(payload, dict) else None
    if not pairs:
        chain_id = "solana" if guessed == "solana" else "ethereum"
        return {
            "key": f"{chain_id}:{address}",
            "source": "名人喊单",
            "chain": CHAIN_LABEL.get(chain_id, chain_id.title()),
            "chain_id": chain_id,
            "symbol": "?",
            "name": "",
            "token_address": address,
            "pair_address": "",
            "price_usd": 0.0,
            "liquidity_usd": 0.0,
            "volume_h1": 0.0,
            "buys": 0,
            "sells": 0,
            "unique_buyers_est": 0,
            "holders": 0,
            "holder_growth_est": 0,
            "price_change_h1": 0.0,
            "fdv": 0.0,
            "url": f"https://dexscreener.com/{chain_id}/{address}",
            "created_at": None,
            "hot": True,
            "unresolved": True,
        }
    pairs = sorted(pairs, key=lambda p: _num((p.get("liquidity") or {}).get("usd")), reverse=True)
    item = _pair_to_item(pairs[0], "名人喊单")
    if not item:
        return None
    item["token_address"] = item.get("token_address") or address
    item["source"] = "名人喊单"
    return item


async def _tweets_for_kols(bearer: str) -> list[dict[str, Any]]:
    handles = [k["handle"] for k in KOL_WATCH]
    query = " OR ".join(f"from:{h}" for h in handles)
    rows: list[dict[str, Any]] = []
    if bearer:
        try:
            rows = await twitter_recent_search(bearer, query, max_results=40)
        except Exception:
            rows = []
    if not rows:
        gathered = await asyncio.gather(
            *[nitter_search(f"from:{h}") for h in handles],
            return_exceptions=True,
        )
        for result in gathered:
            if isinstance(result, Exception):
                continue
            rows.extend(result or [])
    return rows


async def fetch_kol_calls(twitter_bearer: str = "") -> list[dict[str, Any]]:
    """Watch curated KOLs for contract addresses posted in the last day."""
    meta = _kol_by_handle()
    tweets = await _tweets_for_kols((twitter_bearer or "").strip())
    found: dict[str, dict[str, Any]] = {}
    pending: list[tuple[str, str, dict[str, Any], str]] = []
    for tw in tweets:
        handle = str(tw.get("username") or "").lstrip("@")
        info = meta.get(handle.lower())
        if not info:
            continue
        if not tweet_is_fresh(tw.get("created_at") or tw.get("_created")):
            continue
        text = str(tw.get("text") or "")
        cas = extract_cas(text)
        if not cas:
            continue
        for addr, guessed in cas[:3]:
            pending.append((addr, guessed, tw, handle))
    resolved = await asyncio.gather(
        *[_resolve_token(addr, guessed) for addr, guessed, _tw, _h in pending],
        return_exceptions=True,
    )
    for (addr, guessed, tw, handle), item in zip(pending, resolved):
        if isinstance(item, Exception) or not item:
            continue
        info = meta[handle.lower()]
        key = str(item.get("key") or f"{item.get('chain_id')}:{addr}")
        prev = found.get(key)
        callers = list((prev or {}).get("kol_handles") or [])
        if handle.lower() not in {c.lower() for c in callers}:
            callers.append(info["handle"])
        names = list((prev or {}).get("kol_names") or [])
        if info["name"] not in names:
            names.append(info["name"])
        reasons = list((prev or {}).get("kol_reasons") or [])
        if info["reason"] not in reasons:
            reasons.append(info["reason"])
        row = dict(prev or item)
        row.update(item)
        row["key"] = key
        row["kol_call"] = True
        row["kol"] = " / ".join(names)
        row["kol_handles"] = callers
        row["kol_names"] = names
        row["kol_reason"] = "；".join(reasons)
        row["kol_reasons"] = reasons
        row["token_address"] = row.get("token_address") or addr
        row["source"] = "名人喊单"
        row["source_kind"] = "kol"
        row["twitter"] = twitter_url(handle)
        row["url"] = row.get("url") or tw.get("url") or twitter_url(handle)
        row["call_text"] = str(tw.get("text") or "")[:220]
        row["call_url"] = tw.get("url") or ""
        found[key] = row
    return list(found.values())
