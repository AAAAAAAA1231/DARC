from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from web3_radar.collectors.meme import (
    DEXSCREENER,
    GECKO_TERMINAL,
    PUMPFUN,
    _num,
)
from web3_radar.collectors.solana_watch import fmt_cn
from web3_radar.http_util import get_json

SKIP_SYMBOLS = {
    "sol",
    "wsol",
    "usdc",
    "usdt",
    "usd1",
    "dai",
    "btc",
    "wbtc",
    "eth",
    "weth",
}


def parse_created(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        dt = value
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    if isinstance(value, (int, float)):
        n = float(value)
        if n > 1e11:
            n /= 1000.0
        try:
            return datetime.fromtimestamp(n, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    text = str(value).strip()
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def pool_timing(created: datetime | None, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    if created is None:
        return {
            "when_utc": "",
            "when_cn": "",
            "status": "新开盘",
            "relation": "now",
            "label": "发现时间为链上开池时刻（具体到秒以浏览器打开为准）",
            "alert": True,
        }
    delta = now - created
    when_cn = fmt_cn(created)
    if delta <= timedelta(minutes=40):
        status, relation, alert = "正在/刚刚开盘", "now", True
    elif delta <= timedelta(hours=6):
        status, relation, alert = "刚开盘", "now", True
    elif delta <= timedelta(hours=72):
        status, relation, alert = "近三日新池", "past", False
    else:
        status, relation, alert = "已开盘一段时间", "past", False
    return {
        "when_utc": created.isoformat(),
        "when_cn": when_cn,
        "status": status,
        "relation": relation,
        "label": f"开池 {when_cn}",
        "alert": alert,
        "age_hours": round(delta.total_seconds() / 3600.0, 2),
    }


def _symbol_ok(symbol: str, name: str) -> bool:
    sym = (symbol or "").split("/")[0].strip().lower()
    if not sym or sym in SKIP_SYMBOLS:
        return False
    head = (name or "").split("/")[0].strip().lower()
    if head in SKIP_SYMBOLS:
        return False
    return True


def to_onchain_item(
    *,
    key: str,
    name: str,
    symbol: str,
    source: str,
    url: str,
    created: Any,
    liquidity_usd: float = 0.0,
    price_usd: float | None = None,
    fdv: float = 0.0,
    token_address: str = "",
    extra_text: str = "",
    now: datetime | None = None,
) -> dict[str, Any] | None:
    if not _symbol_ok(symbol, name):
        return None
    created_dt = parse_created(created)
    now = now or datetime.now(timezone.utc)
    if created_dt and (now - created_dt) > timedelta(hours=72):
        return None
    timing = pool_timing(created_dt, now=now)
    display = (symbol or name or "未命名").strip()
    full_name = (name or display).strip()
    liq = float(liquidity_usd or 0)
    analysis = (
        f"链上新池，不是 @solana / @toly 关注。"
        f" 来源 {source} · 池子约 ${liq:,.0f}"
        + (f" · FDV ${float(fdv):,.0f}" if fdv else "")
    )
    return {
        "key": key,
        "name": full_name,
        "username": "",
        "kind": "Solana 链上新池",
        "chain": "Solana",
        "text": extra_text or f"{display} 在 Solana 上新开池，时间以链上为准。",
        "analysis": analysis,
        "launch_status": timing["status"],
        "launch_when": timing.get("when_cn") or "",
        "launch_when_label": timing["label"],
        "noticed_at": timing.get("when_cn") or "",
        "alert": bool(timing.get("alert")),
        "alert_level": "high" if timing.get("relation") == "now" else "mid",
        "new_follow": False,
        "watch_kind": "onchain_pool",
        "followed_by": [],
        "official_follow_count": 0,
        "official_follow_total": 0,
        "follow_proof": "",
        "follow_count_label": "不是官方关注 · 链上新开盘",
        "verified_follow": False,
        "url": url,
        "twitter": "",
        "created_at": timing.get("when_utc") or "",
        "source": "链上新池",
        "source_kind": "live",
        "score": int(max(10, min(90, 40 + (20 if timing.get("alert") else 0) + min(30, liq / 2000)))),
        "price_usd": price_usd,
        "liquidity_usd": liq,
        "fdv": float(fdv or 0),
        "followers": 0,
        "token_address": token_address,
        "extra": {"origin": source, "token_address": token_address},
    }


async def _gecko_new_pools() -> list[dict[str, Any]]:
    payload = await get_json(f"{GECKO_TERMINAL}/networks/solana/new_pools", timeout=12.0)
    out: list[dict[str, Any]] = []
    for row in payload.get("data") or []:
        attrs = row.get("attributes") or {}
        name = str(attrs.get("name") or "")
        symbol = name.split(" / ")[0].strip() if name else ""
        addr = str(attrs.get("address") or row.get("id") or "")
        item = to_onchain_item(
            key=f"sol-pool:{addr.lower()}",
            name=name or symbol,
            symbol=symbol,
            source="GeckoTerminal",
            url=f"https://www.geckoterminal.com/solana/pools/{addr}" if addr else "https://www.geckoterminal.com/solana",
            created=attrs.get("pool_created_at"),
            liquidity_usd=_num(attrs.get("reserve_in_usd")),
            price_usd=_num(attrs.get("base_token_price_usd")) or None,
            fdv=_num(attrs.get("fdv_usd") or attrs.get("market_cap_usd")),
            token_address=addr,
        )
        if item:
            out.append(item)
    return out


async def _pump_new_coins() -> list[dict[str, Any]]:
    try:
        data = await get_json(
            f"{PUMPFUN}/coins",
            params={"offset": 0, "limit": 24, "sort": "created_timestamp", "order": "DESC", "includeNsfw": "false"},
            timeout=12.0,
        )
    except Exception:
        data = await get_json(
            "https://frontend-api.pump.fun/coins",
            params={"offset": 0, "limit": 24, "sort": "created_timestamp", "order": "DESC"},
            timeout=12.0,
        )
    if isinstance(data, dict):
        data = data.get("coins") or data.get("data") or []
    out: list[dict[str, Any]] = []
    for coin in data or []:
        if coin.get("nsfw") or coin.get("is_banned"):
            continue
        mint = str(coin.get("mint") or "")
        symbol = str(coin.get("symbol") or "")
        name = str(coin.get("name") or symbol)
        item = to_onchain_item(
            key=f"sol-pump:{mint.lower() or symbol.lower()}",
            name=name,
            symbol=symbol,
            source="Pump.fun",
            url=f"https://pump.fun/{mint}" if mint else "https://pump.fun",
            created=coin.get("created_timestamp"),
            liquidity_usd=_num(coin.get("usd_market_cap")) * 0.15,
            price_usd=None,
            fdv=_num(coin.get("usd_market_cap") or coin.get("market_cap_usd")),
            token_address=mint,
            extra_text=(str(coin.get("description") or "")[:180] or f"{name} 在 Pump.fun 新开盘。"),
        )
        if item:
            out.append(item)
    return out


async def _dex_boosted_solana() -> list[dict[str, Any]]:
    data = await get_json(f"{DEXSCREENER}/token-boosts/latest/v1", timeout=12.0)
    if not isinstance(data, list):
        return []
    addrs = [str(row.get("tokenAddress") or "") for row in data if str(row.get("chainId") or "").lower() == "solana"]
    addrs = [a for a in addrs if a][:12]
    if not addrs:
        return []
    payload = await get_json(f"{DEXSCREENER}/latest/dex/tokens/{','.join(addrs[:10])}", timeout=12.0)
    out: list[dict[str, Any]] = []
    for pair in payload.get("pairs") or []:
        if str(pair.get("chainId") or "").lower() != "solana":
            continue
        token = pair.get("baseToken") or {}
        item = to_onchain_item(
            key=f"sol-dex:{(pair.get('pairAddress') or token.get('address') or token.get('symbol') or '').lower()}",
            name=str(token.get("name") or token.get("symbol") or ""),
            symbol=str(token.get("symbol") or ""),
            source="DexScreener",
            url=str(pair.get("url") or ""),
            created=pair.get("pairCreatedAt"),
            liquidity_usd=_num((pair.get("liquidity") or {}).get("usd")),
            price_usd=_num(pair.get("priceUsd")) or None,
            fdv=_num(pair.get("fdv") or pair.get("marketCap")),
            token_address=str(token.get("address") or ""),
        )
        if item:
            out.append(item)
    return out


async def scan_onchain_launches() -> dict[str, Any]:
    errors: list[str] = []
    fetchers = [
        ("geckoterminal", _gecko_new_pools()),
        ("pump.fun", _pump_new_coins()),
        ("dexscreener", _dex_boosted_solana()),
    ]
    results = await asyncio.gather(*[f[1] for f in fetchers], return_exceptions=True)
    seen: dict[str, dict[str, Any]] = {}
    for (name, _), result in zip(fetchers, results):
        if isinstance(result, Exception):
            errors.append(f"{name}: {result}")
            continue
        for item in result:
            token = str((item.get("token_address") or item.get("key") or "")).lower()
            prev = seen.get(token)
            if prev is None:
                seen[token] = item
                continue
            if float(item.get("liquidity_usd") or 0) > float(prev.get("liquidity_usd") or 0):
                seen[token] = item
    items = list(seen.values())
    items.sort(key=lambda x: (not x.get("alert"), -(x.get("score") or 0)))
    return {
        "items": items[:24],
        "errors": errors,
        "count": min(len(items), 24),
    }
