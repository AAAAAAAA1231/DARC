from __future__ import annotations

import asyncio
import re
from datetime import datetime, timezone
from typing import Any

from web3_radar.engine.meme_score import enrich_and_score, select_watchlist
from web3_radar.http_util import get_json as _get_json_util

DEXSCREENER = "https://api.dexscreener.com"
PUMPFUN = "https://frontend-api-v3.pump.fun"
GMGN_SOL_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/sol/swaps/1h"
GMGN_ETH_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/eth/swaps/1h"
GMGN_BSC_TRENDING = "https://gmgn.ai/defi/quotation/v1/rank/bsc/swaps/1h"
GECKO_TERMINAL = "https://api.geckoterminal.com/api/v2"

MEME_MENTION_QUERIES = [
    '("CA:" OR "contract:" OR "$") (solana OR pump OR meme OR base)',
    '"fair launch" (CA OR mint OR $)',
    "(新币 OR 发射 OR meme) (CA OR 合约 OR $)",
]
MEME_MAX_AGE_DAYS = 3
TICKER_RE = re.compile(r"\$([A-Za-z]{2,12})\b")
DEX_SEARCH = "https://api.dexscreener.com/latest/dex/search"
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


def meme_age_ok(item: dict[str, Any], max_days: int = MEME_MAX_AGE_DAYS) -> bool:
    from web3_radar.engine.meme_score import _age_minutes

    age = _age_minutes(item)
    if age is None:
        return False
    return age <= max_days * 24 * 60


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
        "buys_m5": buys_m5,
        "sells_m5": sells_m5,
        "unique_buyers_est": max(buyers, buys_m5, int(buys * 0.4)),
        "holders": holders,
        "holder_growth_est": max(0, buys_m5, int(buys * 0.2)),
        "price_change_h1": price_change,
        "price_change_m5": price_change_m5,
        "volume_m5": volume_m5,
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
            items.append(
                {
                    "key": f"{network}:{addr}",
                    "source": "geckoterminal",
                    "chain": label,
                    "chain_id": network,
                    "symbol": attrs.get("name") or attrs.get("base_token_price_quote_token") or "?",
                    "name": attrs.get("name") or "",
                    "token_address": str(addr),
                    "pair_address": attrs.get("address") or "",
                    "price_usd": _num(attrs.get("base_token_price_usd")),
                    "liquidity_usd": liq,
                    "volume_h1": _num(attrs.get("volume_usd", {}).get("h1") if isinstance(attrs.get("volume_usd"), dict) else 0),
                    "buys": buys,
                    "sells": 0,
                    "unique_buyers_est": max(buys, 8 if liq >= 20000 else 0),
                    "holders": 0,
                    "holder_growth_est": max(5, buys // 3),
                    "price_change_h1": _num((attrs.get("price_change_percentage") or {}).get("h1")),
                    "fdv": _num(attrs.get("fdv_usd") or attrs.get("market_cap_usd")),
                    "url": f"https://www.geckoterminal.com/{network}/pools/{attrs.get('address') or ''}",
                    "created_at": attrs.get("pool_created_at"),
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
                    "holder_growth_est": max(0, buys // 2),
                    "price_change_h1": _num(chg.get("h1")),
                    "price_change_m5": _num(chg.get("m5")),
                    "fdv": _num(attrs.get("fdv_usd") or attrs.get("market_cap_usd")),
                    "url": f"https://www.geckoterminal.com/{network}/pools/{attrs.get('address') or ''}",
                    "created_at": attrs.get("pool_created_at"),
                    "hot": True,
                }
            )
    return items


async def _resolve_symbol(symbol: str) -> dict[str, Any] | None:
    try:
        data = await _get_json(DEX_SEARCH, params={"q": symbol})
    except Exception:
        return None
    pairs = data.get("pairs") if isinstance(data, dict) else None
    if not isinstance(pairs, list) or not pairs:
        return None
    want = symbol.lower()
    matched = [
        p for p in pairs
        if str((p.get("baseToken") or {}).get("symbol") or "").lower() == want
    ]
    pool = matched or pairs
    pool = sorted(pool, key=lambda p: _num((p.get("liquidity") or {}).get("usd")), reverse=True)
    return _pair_to_item(pool[0], "twitter24h")


async def fetch_mentioned_memes(twitter_bearer: str = "") -> list[dict[str, Any]]:
    """Tokens mentioned on X in the last 24h whose pair is not older than 3 days."""
    from web3_radar.collectors.kol_calls import _resolve_token, extract_cas
    from web3_radar.collectors.social import collect_social
    from web3_radar.engine.meme_score import _age_minutes

    try:
        tweets = await asyncio.wait_for(
            collect_social(MEME_MENTION_QUERIES, twitter_bearer, lookback_days=1),
            timeout=9,
        )
    except Exception:
        tweets = []
    counts: dict[str, int] = {}
    sample: dict[str, tuple[str, str]] = {}
    tickers: dict[str, int] = {}
    for tw in tweets:
        text = tw.get("text") or ""
        for addr, chain in extract_cas(text):
            key = "ca:" + addr.lower()
            counts[key] = counts.get(key, 0) + 1
            sample[key] = (addr, chain)
        for m in TICKER_RE.findall(text):
            tickers[m.upper()] = tickers.get(m.upper(), 0) + 1
    items: list[dict[str, Any]] = []
    for key, n in sorted(counts.items(), key=lambda x: -x[1])[:25]:
        addr, chain = sample[key]
        try:
            row = await _resolve_token(addr, chain)
        except Exception:
            row = None
        if not row:
            continue
        age = _age_minutes(row)
        if age is not None and age > MEME_MAX_AGE_DAYS * 24 * 60:
            continue
        row["mention_count"] = n
        row["source"] = "+".join(x for x in [str(row.get("source") or ""), "twitter24h"] if x)
        items.append(row)
    seen_sym = {str(x.get("symbol") or "").upper() for x in items}
    for sym, n in sorted(tickers.items(), key=lambda x: -x[1])[:15]:
        if sym in seen_sym:
            for row in items:
                if str(row.get("symbol") or "").upper() == sym:
                    row["mention_count"] = int(row.get("mention_count") or 0) + n
            continue
        try:
            row = await _resolve_symbol(sym)
        except Exception:
            row = None
        if not row:
            continue
        age = _age_minutes(row)
        if age is not None and age > MEME_MAX_AGE_DAYS * 24 * 60:
            continue
        row["mention_count"] = n
        row["source"] = "twitter24h"
        items.append(row)
        seen_sym.add(sym)
    items.sort(key=lambda x: int(x.get("mention_count") or 0), reverse=True)
    return items


async def scan_meme_coins(
    min_liquidity_usd: float = 1_000_000,
    min_unique_buyers: int = 8,
    min_holder_growth: int = 5,
    twitter_bearer: str = "",
) -> dict[str, Any]:
    from web3_radar.collectors.kol_calls import fetch_kol_calls
    from web3_radar.engine.meme_score import _age_minutes

    errors: list[str] = []
    mentioned: list[dict[str, Any]] = []
    try:
        mentioned = await fetch_mentioned_memes(twitter_bearer)
    except Exception as exc:
        errors.append(f"twitter_mentions: {exc}")

    cutoff = MEME_MAX_AGE_DAYS * 24 * 60
    ranked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in mentioned:
        extra = enrich_and_score(item, min_liquidity_usd)
        extra["mention_count"] = item.get("mention_count")
        extra["source_kind"] = "twitter"
        if extra.get("grade") == "避开":
            extra["grade"] = "观察"
            extra["followable"] = False
        ranked.append(extra)
        seen.add(extra["key"])

    if not ranked:
        collected: list[dict[str, Any]] = []
        fetchers = [
            ("kol_calls", fetch_kol_calls(twitter_bearer)),
            ("dexscreener_boosted", fetch_dexscreener_boosted()),
            ("geckoterminal_new", fetch_geckoterminal_new()),
        ]
        results = await asyncio.gather(*[f[1] for f in fetchers], return_exceptions=True)
        for (name, _), result in zip(fetchers, results):
            if isinstance(result, Exception):
                errors.append(f"{name}: {result}")
                continue
            collected.extend(result)
        for item in collected:
            age = _age_minutes(item)
            if age is None or age > cutoff:
                continue
            extra = enrich_and_score(item, min_liquidity_usd)
            if extra["key"] in seen:
                continue
            extra["source_kind"] = extra.get("source_kind") or "chain"
            ranked.append(extra)
            seen.add(extra["key"])

    ranked.sort(
        key=lambda x: (
            int(x.get("mention_count") or 0),
            1 if x.get("kol_call") else 0,
            {"可跟": 3, "观察": 2, "避开": 1}.get(str(x.get("grade") or ""), 0),
        ),
        reverse=True,
    )
    followable = [x for x in ranked if x.get("followable")]
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "min_liquidity_usd": min_liquidity_usd,
        "count": len(ranked),
        "followable_count": len(followable),
        "kol_count": sum(1 for x in ranked if x.get("kol_call")),
        "items": ranked,
        "errors": errors,
        "mention_count": sum(int(x.get("mention_count") or 0) for x in ranked),
        "method": "刷新后只按过去 24 小时推特提及排序，发币超过 3 天的丢掉。可跟仍要求池子 ≥ $1M。",
    }
