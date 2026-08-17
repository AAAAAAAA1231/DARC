from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

DEXSCREENER = "https://api.dexscreener.com"
PUMPFUN = "https://frontend-api-v3.pump.fun"
GMGN_SOL_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/sol/swaps/1h"
GMGN_ETH_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/eth/swaps/1h"
GMGN_BSC_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/bsc/swaps/1h"

CHAIN_LABEL = {
    "solana": "Solana",
    "ethereum": "Ethereum",
    "bsc": "BSC",
    "base": "Base",
    "arbitrum": "Arbitrum",
    "polygon": "Polygon",
    "avalanche": "Avalanche",
    "blast": "Blast",
    "optimism": "Optimism",
    "tron": "Tron",
}


def _num(v: Any, default: float = 0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


async def _get_json(url: str, params: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> Any:
    default_headers = {
        "User-Agent": "ChainRadar/1.0",
        "Accept": "application/json",
    }
    if headers:
        default_headers.update(headers)
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        resp = await client.get(url, params=params, headers=default_headers)
        resp.raise_for_status()
        return resp.json()


def _pair_to_item(pair: dict[str, Any], source: str) -> dict[str, Any] | None:
    liq = _num((pair.get("liquidity") or {}).get("usd"))
    txns = pair.get("txns") or {}
    m5 = txns.get("m5") or {}
    h1 = txns.get("h1") or {}
    buys = int(_num(m5.get("buys")) + _num(h1.get("buys")))
    sells = int(_num(m5.get("sells")) + _num(h1.get("sells")))
    buyers = int(_num((pair.get("makers") or {}).get("h1")) or _num(h1.get("buys")))
    volume_h1 = _num((pair.get("volume") or {}).get("h1"))
    price_change = _num((pair.get("priceChange") or {}).get("h1"))
    holders = int(_num(pair.get("holders") or (pair.get("info") or {}).get("holders")))
    chain = pair.get("chainId") or pair.get("chain") or "unknown"
    token = pair.get("baseToken") or {}
    created = pair.get("pairCreatedAt")
    return {
        "key": f"{chain}:{(token.get('address') or pair.get('pairAddress') or token.get('name') or '')}",
        "source": source,
        "chain": CHAIN_LABEL.get(str(chain).lower(), str(chain)),
        "chain_id": chain,
        "symbol": token.get("symbol") or pair.get("symbol") or "?",
        "name": token.get("name") or "",
        "token_address": token.get("address") or "",
        "pair_address": pair.get("pairAddress") or "",
        "price_usd": _num(pair.get("priceUsd") or pair.get("price")),
        "liquidity_usd": liq,
        "volume_h1": volume_h1,
        "buys": buys,
        "sells": sells,
        "unique_buyers_est": max(buyers, buys),
        "holders": holders,
        "holder_growth_est": max(0, int(buys * 0.35)),
        "price_change_h1": price_change,
        "fdv": _num(pair.get("fdv") or pair.get("marketCap")),
        "url": pair.get("url") or "",
        "created_at": created,
        "hot": True,
    }


def _passes_meme_filter(item: dict[str, Any], min_liq: float, min_buyers: int, min_holder_growth: int) -> bool:
    if item["liquidity_usd"] < min_liq:
        return False
    if item["unique_buyers_est"] < min_buyers and item["buys"] < min_buyers:
        return False
    if item["holder_growth_est"] < min_holder_growth and item["buys"] < min_buyers * 2:
        return False
    return True


async def fetch_dexscreener_boosted() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in ("/token-boosts/latest/v1", "/token-boosts/top/v1", "/token-profiles/latest/v1"):
        try:
            data = await _get_json(DEXSCREENER + path)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        tokens = []
        for row in data[:40]:
            chain = row.get("chainId")
            addr = row.get("tokenAddress")
            if chain and addr:
                tokens.append(f"{chain}:{addr}")
        if not tokens:
            continue
        # Dexscreener allows batch token lookup
        for chunk_start in range(0, min(len(tokens), 30), 10):
            chunk = tokens[chunk_start : chunk_start + 10]
            addrs = ",".join(t.split(":", 1)[1] for t in chunk)
            try:
                payload = await _get_json(f"{DEXSCREENER}/latest/dex/tokens/{addrs}")
            except Exception:
                continue
            for pair in payload.get("pairs") or []:
                item = _pair_to_item(pair, "dexscreener")
                if item:
                    items.append(item)
    return items


async def fetch_dexscreener_search(query: str) -> list[dict[str, Any]]:
    try:
        payload = await _get_json(f"{DEXSCREENER}/latest/dex/search", params={"q": query})
    except Exception:
        return []
    items = []
    for pair in (payload.get("pairs") or [])[:50]:
        item = _pair_to_item(pair, "dexscreener")
        if item:
            items.append(item)
    return items


async def fetch_pumpfun(limit: int = 50) -> list[dict[str, Any]]:
    try:
        data = await _get_json(
            f"{PUMPFUN}/coins",
            params={"offset": 0, "limit": limit, "sort": "last_trade_timestamp", "order": "DESC", "includeNsfw": "false"},
        )
    except Exception:
        try:
            data = await _get_json("https://frontend-api.pump.fun/coins", params={"offset": 0, "limit": limit, "sort": "last_trade_timestamp"})
        except Exception:
            return []
    if isinstance(data, dict):
        data = data.get("coins") or data.get("data") or []
    items = []
    for coin in data or []:
        usd_liq = _num(coin.get("usd_market_cap")) * 0.02 + _num(coin.get("virtual_sol_reserves")) * 0.000001
        # pump.fun virtual liquidity is in lamports-like sol reserves
        sol_reserves = _num(coin.get("virtual_sol_reserves")) / 1e9
        liq_usd = sol_reserves * 140  # rough SOL px fallback, refined if usd_market_cap present
        if coin.get("usd_market_cap"):
            liq_usd = max(liq_usd, _num(coin.get("usd_market_cap")) * 0.15)
        reply = int(_num(coin.get("reply_count")))
        items.append(
            {
                "key": f"solana:{coin.get('mint') or coin.get('symbol')}",
                "source": "pump.fun",
                "chain": "Solana",
                "chain_id": "solana",
                "symbol": coin.get("symbol") or "?",
                "name": coin.get("name") or "",
                "token_address": coin.get("mint") or "",
                "pair_address": coin.get("bonding_curve") or "",
                "price_usd": _num(coin.get("usd_market_cap")) / max(_num(coin.get("total_supply"), 1_000_000_000), 1),
                "liquidity_usd": liq_usd,
                "volume_h1": _num(coin.get("volume_24h") or coin.get("virtual_token_reserves")) / 24,
                "buys": int(_num(coin.get("unique_holders"))) + reply,
                "sells": 0,
                "unique_buyers_est": int(_num(coin.get("unique_holders"))),
                "holders": int(_num(coin.get("unique_holders"))),
                "holder_growth_est": max(1, int(_num(coin.get("unique_holders")) * 0.1)),
                "price_change_h1": 0.0,
                "fdv": _num(coin.get("usd_market_cap")),
                "url": f"https://pump.fun/{coin.get('mint', '')}",
                "created_at": coin.get("created_timestamp"),
                "hot": True,
            }
        )
    return items


async def fetch_gmgn(chain_url: str, chain_label: str) -> list[dict[str, Any]]:
    try:
        data = await _get_json(chain_url, params={"orderby": "swaps", "direction": "desc"})
    except Exception:
        return []
    rows = (((data or {}).get("data") or {}).get("rank")) or data.get("rank") or []
    items = []
    for row in rows[:40]:
        addr = row.get("address") or row.get("token_address") or ""
        holders = int(_num(row.get("holder_count")))
        buys = int(_num(row.get("buys") or row.get("buy_swaps_1h") or row.get("swaps_1h")))
        items.append(
            {
                "key": f"{chain_label.lower()}:{addr}",
                "source": "gmgn",
                "chain": chain_label,
                "chain_id": chain_label.lower(),
                "symbol": row.get("symbol") or "?",
                "name": row.get("name") or "",
                "token_address": addr,
                "pair_address": row.get("pool") or "",
                "price_usd": _num(row.get("price")),
                "liquidity_usd": _num(row.get("liquidity")),
                "volume_h1": _num(row.get("volume_1h") or row.get("volume")),
                "buys": buys,
                "sells": int(_num(row.get("sells") or row.get("sell_swaps_1h"))),
                "unique_buyers_est": int(_num(row.get("unique_wallets_1h") or row.get("smart_degen_count") or buys)),
                "holders": holders,
                "holder_growth_est": int(_num(row.get("holder_count_change") or row.get("holder_change_1h") or max(0, buys * 0.2))),
                "price_change_h1": _num(row.get("price_change_percent1h") or row.get("price_change_1h")),
                "fdv": _num(row.get("market_cap") or row.get("fdv")),
                "url": f"https://gmgn.ai/{chain_label.lower()}/token/{addr}",
                "created_at": row.get("open_timestamp"),
                "hot": True,
            }
        )
    return items


async def scan_meme_coins(
    min_liquidity_usd: float = 20_000,
    min_unique_buyers: int = 8,
    min_holder_growth: int = 5,
) -> dict[str, Any]:
    errors: list[str] = []
    collected: list[dict[str, Any]] = []
    fetchers = [
        ("dexscreener_boosted", fetch_dexscreener_boosted()),
        ("dexscreener_sol", fetch_dexscreener_search("SOL")),
        ("pumpfun", fetch_pumpfun()),
        ("gmgn_sol", fetch_gmgn(GMGN_SOL_TRENDING, "Solana")),
        ("gmgn_eth", fetch_gmgn(GMGN_ETH_TRENDING, "Ethereum")),
        ("gmgn_bsc", fetch_gmgn(GMGN_BSC_TRENDING, "BSC")),
    ]
    import asyncio

    results = await asyncio.gather(*[f[1] for f in fetchers], return_exceptions=True)
    for (name, _), result in zip(fetchers, results):
        if isinstance(result, Exception):
            errors.append(f"{name}: {result}")
            continue
        collected.extend(result)

    merged: dict[str, dict[str, Any]] = {}
    for item in collected:
        key = item["key"]
        if key not in merged:
            merged[key] = item
            continue
        # keep the richer record
        if item["liquidity_usd"] > merged[key]["liquidity_usd"]:
            sources = {merged[key]["source"], item["source"]}
            merged[key] = item
            merged[key]["source"] = "+".join(sorted(sources))
        else:
            merged[key]["unique_buyers_est"] = max(merged[key]["unique_buyers_est"], item["unique_buyers_est"])
            merged[key]["holders"] = max(merged[key]["holders"], item["holders"])

    filtered = [
        it
        for it in merged.values()
        if _passes_meme_filter(it, min_liquidity_usd, min_unique_buyers, min_holder_growth)
    ]
    filtered.sort(key=lambda x: (x["unique_buyers_est"] + x["holder_growth_est"], x["liquidity_usd"]), reverse=True)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "min_liquidity_usd": min_liquidity_usd,
        "count": len(filtered),
        "items": filtered[:80],
        "errors": errors,
    }
