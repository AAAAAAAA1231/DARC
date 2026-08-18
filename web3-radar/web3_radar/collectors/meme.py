from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web3_radar.engine.meme_score import period_pick, select_watchlist
from web3_radar.http_util import get_json as _get_json_util

DEXSCREENER = "https://api.dexscreener.com"
PUMPFUN = "https://frontend-api-v3.pump.fun"
GMGN_SOL_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/sol/swaps/1h"
GMGN_ETH_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/eth/swaps/1h"
GMGN_BSC_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/bsc/swaps/1h"
GECKO_TERMINAL = "https://api.geckoterminal.com/api/v2"

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
    return await _get_json_util(url, params=params)


def _pair_to_item(pair: dict[str, Any], source: str) -> dict[str, Any] | None:
    liq = _num((pair.get("liquidity") or {}).get("usd"))
    txns = pair.get("txns") or {}
    m5 = txns.get("m5") or {}
    h1 = txns.get("h1") or {}
    buys_m5 = int(_num(m5.get("buys")))
    sells_m5 = int(_num(m5.get("sells")))
    buys = buys_m5 + int(_num(h1.get("buys")))
    sells = sells_m5 + int(_num(h1.get("sells")))
    buyers = int(_num((pair.get("makers") or {}).get("h1")) or buys_m5 or _num(h1.get("buys")))
    volume_h1 = _num((pair.get("volume") or {}).get("h1"))
    volume_m5 = _num((pair.get("volume") or {}).get("m5"))
    price_change = _num((pair.get("priceChange") or {}).get("h1"))
    price_change_m5 = _num((pair.get("priceChange") or {}).get("m5"))
    price_change_h6 = _num((pair.get("priceChange") or {}).get("h6"))
    price_change_h24 = _num((pair.get("priceChange") or {}).get("h24"))
    holders = int(_num(pair.get("holders") or (pair.get("info") or {}).get("holders")))
    chain = pair.get("chainId") or pair.get("chain") or "unknown"
    token = pair.get("baseToken") or {}
    created = pair.get("pairCreatedAt")
    info = pair.get("info") or {}
    socials = info.get("socials") or []
    websites = info.get("websites") or []
    links = list(socials) + list(websites)
    blob = " ".join(str(x) for x in links).lower()
    h24 = txns.get("h24") or {}
    buys_h24 = int(_num(h24.get("buys")))
    sells_h24 = int(_num(h24.get("sells")))
    volume_h24 = _num((pair.get("volume") or {}).get("h24"))
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
        "volume_h24": volume_h24,
        "buys": buys_h24 or buys,
        "sells": sells_h24 or sells,
        "buys_m5": buys_m5,
        "sells_m5": sells_m5,
        "buys_h24": buys_h24,
        "sells_h24": sells_h24,
        "unique_buyers_est": max(buyers, buys_m5, buys_h24),
        "holders": holders,
        "holder_growth_est": max(0, int(_num((pair.get("info") or {}).get("holderChange") or 0))),
        "price_change_h1": price_change,
        "price_change_m5": price_change_m5,
        "price_change_h6": price_change_h6,
        "price_change_h24": price_change_h24,
        "volume_m5": volume_m5,
        "fdv": _num(pair.get("fdv") or pair.get("marketCap")),
        "url": pair.get("url") or "",
        "created_at": created,
        "links": links,
        "has_twitter": "twitter" in blob or "x.com" in blob,
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


async def _pairs_for_addresses(addresses: list[str], source: str, meta: dict[str, dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    meta = meta or {}
    for chunk_start in range(0, min(len(addresses), 40), 10):
        chunk = addresses[chunk_start : chunk_start + 10]
        try:
            payload = await _get_json(f"{DEXSCREENER}/latest/dex/tokens/{','.join(chunk)}")
        except Exception:
            continue
        for pair in payload.get("pairs") or []:
            item = _pair_to_item(pair, source)
            if not item:
                continue
            extra = meta.get((item.get("token_address") or "").lower()) or {}
            if extra.get("totalAmount") or extra.get("amount"):
                item["boost_amount"] = _num(extra.get("totalAmount") or extra.get("amount"))
            if extra.get("links"):
                item["links"] = list(item.get("links") or []) + list(extra.get("links") or [])
                blob = " ".join(str(x) for x in item["links"]).lower()
                item["has_twitter"] = bool(item.get("has_twitter")) or "twitter" in blob or "x.com" in blob
            if extra.get("claimDate") or extra.get("is_cto"):
                item["is_cto"] = True
            if extra.get("description"):
                item["description"] = extra.get("description")
            items.append(item)
    return items


async def fetch_dexscreener_boosted() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for path in ("/token-boosts/latest/v1", "/token-boosts/top/v1", "/token-profiles/latest/v1"):
        try:
            data = await _get_json(DEXSCREENER + path)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        meta: dict[str, dict[str, Any]] = {}
        addrs: list[str] = []
        for row in data[:40]:
            addr = row.get("tokenAddress")
            if not addr:
                continue
            addrs.append(addr)
            meta[str(addr).lower()] = row
        if addrs:
            items.extend(await _pairs_for_addresses(addrs, "dexscreener", meta))
    return items


async def fetch_dexscreener_takeovers() -> list[dict[str, Any]]:
    try:
        data = await _get_json(DEXSCREENER + "/community-takeovers/latest/v1")
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    meta: dict[str, dict[str, Any]] = {}
    addrs: list[str] = []
    for row in data[:30]:
        addr = row.get("tokenAddress")
        if not addr:
            continue
        row = dict(row)
        row["is_cto"] = True
        addrs.append(addr)
        meta[str(addr).lower()] = row
    return await _pairs_for_addresses(addrs, "cto", meta)


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


async def fetch_geckoterminal() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for network, label in (("solana", "Solana"), ("bsc", "BSC"), ("base", "Base"), ("eth", "Ethereum")):
        try:
            payload = await _get_json(f"{GECKO_TERMINAL}/networks/{network}/trending_pools")
        except Exception:
            continue
        for row in (payload.get("data") or [])[:25]:
            attrs = row.get("attributes") or {}
            rel = ((row.get("relationships") or {}).get("base_token") or {}).get("data") or {}
            liq = _num(attrs.get("reserve_in_usd"))
            buys = int(_num((attrs.get("transactions") or {}).get("h1", {}).get("buys") if isinstance(attrs.get("transactions"), dict) else 0))
            if isinstance(attrs.get("transactions"), dict):
                h1 = attrs["transactions"].get("h1") or {}
                buys = int(_num(h1.get("buys")))
            addr = rel.get("id") or row.get("id") or attrs.get("address") or ""
            addr = str(addr)
            if "_" in addr:
                addr = addr.split("_", 1)[-1]
            chg = attrs.get("price_change_percentage") if isinstance(attrs.get("price_change_percentage"), dict) else {}
            vol = attrs.get("volume_usd") if isinstance(attrs.get("volume_usd"), dict) else {}
            txs = attrs.get("transactions") or {}
            h1 = txs.get("h1") if isinstance(txs, dict) else {}
            h24 = txs.get("h24") if isinstance(txs, dict) else {}
            m5 = txs.get("m5") if isinstance(txs, dict) else {}
            items.append(
                {
                    "key": f"{network}:{addr}",
                    "source": "geckoterminal",
                    "chain": label,
                    "chain_id": network,
                    "symbol": (attrs.get("name") or "?").split(" / ")[0][:16],
                    "name": attrs.get("name") or "",
                    "token_address": str(addr),
                    "pair_address": attrs.get("address") or "",
                    "price_usd": _num(attrs.get("base_token_price_usd")),
                    "liquidity_usd": liq,
                    "volume_h1": _num(vol.get("h1")),
                    "volume_h24": _num(vol.get("h24")),
                    "buys": int(_num((h24 or {}).get("buys") or (h1 or {}).get("buys"))),
                    "sells": int(_num((h24 or {}).get("sells") or (h1 or {}).get("sells"))),
                    "buys_m5": int(_num((m5 or {}).get("buys"))),
                    "sells_m5": int(_num((m5 or {}).get("sells"))),
                    "unique_buyers_est": int(_num((h24 or {}).get("buys") or (h1 or {}).get("buys"))),
                    "holders": 0,
                    "holder_growth_est": 0,
                    "price_change_h1": _num(chg.get("h1")),
                    "price_change_h6": _num(chg.get("h6")),
                    "price_change_h24": _num(chg.get("h24")),
                    "price_change_m5": _num(chg.get("m5")),
                    "fdv": _num(attrs.get("fdv_usd") or attrs.get("market_cap_usd")),
                    "url": f"https://www.geckoterminal.com/{network}/pools/{attrs.get('address') or ''}",
                    "created_at": attrs.get("pool_created_at"),
                    "gecko_trending": True,
                    "hot": True,
                }
            )
    return items


async def fetch_geckoterminal_new() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for network, label in (("solana", "Solana"), ("bsc", "BSC"), ("base", "Base")):
        try:
            payload = await _get_json(f"{GECKO_TERMINAL}/networks/{network}/new_pools")
        except Exception:
            continue
        for row in (payload.get("data") or [])[:20]:
            attrs = row.get("attributes") or {}
            liq = _num(attrs.get("reserve_in_usd"))
            txs = attrs.get("transactions") or {}
            h1 = txs.get("h1") if isinstance(txs, dict) else {}
            m5 = txs.get("m5") if isinstance(txs, dict) else {}
            buys = int(_num((m5 or {}).get("buys") or (h1 or {}).get("buys")))
            sells = int(_num((m5 or {}).get("sells") or (h1 or {}).get("sells")))
            addr = attrs.get("address") or row.get("id") or ""
            vol = attrs.get("volume_usd") if isinstance(attrs.get("volume_usd"), dict) else {}
            chg = attrs.get("price_change_percentage") if isinstance(attrs.get("price_change_percentage"), dict) else {}
            items.append(
                {
                    "key": f"{network}:{addr}",
                    "source": "geckoterminal-new",
                    "chain": label,
                    "chain_id": network,
                    "symbol": (attrs.get("name") or "?").split(" / ")[0][:16],
                    "name": attrs.get("name") or "",
                    "token_address": str(addr),
                    "pair_address": attrs.get("address") or "",
                    "price_usd": _num(attrs.get("base_token_price_usd")),
                    "liquidity_usd": liq,
                    "volume_h1": _num(vol.get("h1")),
                    "volume_m5": _num(vol.get("m5")),
                    "buys": buys,
                    "sells": sells,
                    "buys_m5": int(_num((m5 or {}).get("buys"))),
                    "sells_m5": int(_num((m5 or {}).get("sells"))),
                    "unique_buyers_est": buys,
                    "holders": 0,
                    "holder_growth_est": max(0, buys // 2) if buys else 0,
                    "price_change_h1": _num(chg.get("h1")),
                    "price_change_m5": _num(chg.get("m5")),
                    "fdv": _num(attrs.get("fdv_usd") or attrs.get("market_cap_usd")),
                    "url": f"https://www.geckoterminal.com/{network}/pools/{attrs.get('address') or ''}",
                    "created_at": attrs.get("pool_created_at"),
                    "hot": True,
                }
            )
    return items


async def scan_meme_coins(
    min_liquidity_usd: float = 100_000,
    min_unique_buyers: int = 15,
    min_holder_growth: int = 8,
) -> dict[str, Any]:
    errors: list[str] = []
    collected: list[dict[str, Any]] = []
    fetchers = [
        ("dexscreener_boosted", fetch_dexscreener_boosted()),
        ("dexscreener_cto", fetch_dexscreener_takeovers()),
        ("gmgn_sol", fetch_gmgn(GMGN_SOL_TRENDING, "Solana")),
        ("gmgn_eth", fetch_gmgn(GMGN_ETH_TRENDING, "Ethereum")),
        ("gmgn_bsc", fetch_gmgn(GMGN_BSC_TRENDING, "BSC")),
        ("geckoterminal", fetch_geckoterminal()),
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
        old = merged[key]
        richer = item if item["liquidity_usd"] > old["liquidity_usd"] else old
        other = old if richer is item else item
        sources = {old.get("source"), item.get("source")}
        richer = dict(richer)
        richer["source"] = "+".join(sorted(x for x in sources if x))
        richer["unique_buyers_est"] = max(_num(old.get("unique_buyers_est")), _num(item.get("unique_buyers_est")))
        richer["holders"] = max(int(_num(old.get("holders"))), int(_num(item.get("holders"))))
        richer["has_twitter"] = bool(old.get("has_twitter") or item.get("has_twitter"))
        richer["is_cto"] = bool(old.get("is_cto") or item.get("is_cto"))
        richer["gecko_trending"] = bool(old.get("gecko_trending") or item.get("gecko_trending"))
        richer["boost_amount"] = max(_num(old.get("boost_amount")), _num(item.get("boost_amount")))
        richer["links"] = list(old.get("links") or []) + list(item.get("links") or [])
        if other.get("price_change_h6") and not richer.get("price_change_h6"):
            richer["price_change_h6"] = other.get("price_change_h6")
        if other.get("volume_h24") and _num(richer.get("volume_h24")) < _num(other.get("volume_h24")):
            richer["volume_h24"] = other.get("volume_h24")
        merged[key] = richer

    ranked = select_watchlist(list(merged.values()), min_liquidity_usd)
    followable = [x for x in ranked if x.get("followable")]
    pick = period_pick(ranked)
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "min_liquidity_usd": min_liquidity_usd,
        "count": len(ranked),
        "followable_count": len(followable),
        "period_pick": pick,
        "items": ranked,
        "errors": errors,
        "method": "一个月一买：meme 币，成功率优先还要留倍数。只挑活过 3 天、池子够出、市值还小、买盘和 X/社区热度确认的票。飞刀K、过新盘、已经上千万的老币一律避开。2 倍先锁 35%，剩下拿到本月。",
    }
