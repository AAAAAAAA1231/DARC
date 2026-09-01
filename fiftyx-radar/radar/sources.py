from __future__ import annotations

import json
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Optional

from .models import TokenSnapshot

GECKO_TERMINAL = "https://api.geckoterminal.com/api/v2"
DEXSCREENER = "https://api.dexscreener.com"
USER_AGENT = "fiftyx-radar/0.1 (research scanner; not investment advice)"

DEFAULT_NETWORKS = (
    "robinhood",
    "hyperevm",
    "solana",
    "bsc",
    "base",
    "abstract",
    "unichain",
)

QUOTE_BLACKLIST = {
    "usdt",
    "usdc",
    "usd",
    "usdg",
    "busd",
    "dai",
    "weth",
    "wbnb",
    "wsol",
    "sol",
    "eth",
    "bnb",
    "hype",
    "whype",
}


def _get_json(url: str, timeout: int = 25) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None


def _f(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _parse_dt(value: Any) -> Optional[datetime]:
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _index_included(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in payload.get("included") or []:
        key = f"{item.get('type')}:{item.get('id')}"
        out[key] = item
    return out


def _rel_id(node: dict[str, Any], rel: str) -> Optional[str]:
    data = ((node.get("relationships") or {}).get(rel) or {}).get("data") or {}
    return data.get("id")


def pools_to_snapshots(payload: dict[str, Any], *, chain: str, source: str) -> list[TokenSnapshot]:
    included = _index_included(payload)
    snapshots: list[TokenSnapshot] = []
    for pool in payload.get("data") or []:
        attrs = pool.get("attributes") or {}
        base_id = _rel_id(pool, "base_token")
        quote_id = _rel_id(pool, "quote_token")
        dex_id = _rel_id(pool, "dex") or ""
        base = included.get(f"token:{base_id}", {})
        quote = included.get(f"token:{quote_id}", {})
        dex = included.get(f"dex:{dex_id}", {})
        base_attr = base.get("attributes") or {}
        quote_attr = quote.get("attributes") or {}
        dex_attr = dex.get("attributes") or {}

        symbol = (base_attr.get("symbol") or "").lstrip("$")
        quote_symbol = (quote_attr.get("symbol") or "").lstrip("$")
        if symbol.lower() in QUOTE_BLACKLIST and quote_symbol.lower() not in QUOTE_BLACKLIST:
            base_attr, quote_attr = quote_attr, base_attr
            symbol = (base_attr.get("symbol") or "").lstrip("$")

        if symbol.lower() in QUOTE_BLACKLIST:
            continue

        tx = (attrs.get("transactions") or {}).get("h24") or {}
        vol = attrs.get("volume_usd") or {}
        change = attrs.get("price_change_percentage") or {}
        address = base_attr.get("address") or ""
        pair = attrs.get("address") or ""
        chain_slug = chain
        url = f"https://www.geckoterminal.com/{chain_slug}/pools/{pair}" if pair else ""

        snapshots.append(
            TokenSnapshot(
                chain=chain_slug,
                dex=(dex_id or dex_attr.get("name") or "unknown").lower(),
                name=base_attr.get("name") or symbol or "unknown",
                symbol=symbol or "?",
                address=address,
                pair_address=pair,
                price_usd=_f(attrs.get("base_token_price_usd")),
                fdv_usd=_f(attrs.get("fdv_usd")),
                mcap_usd=_f(attrs.get("market_cap_usd")),
                liquidity_usd=_f(attrs.get("reserve_in_usd")),
                volume_h24=_f(vol.get("h24")),
                buys_h24=_i(tx.get("buys")),
                sells_h24=_i(tx.get("sells")),
                buyers_h24=_i(tx.get("buyers")),
                sellers_h24=_i(tx.get("sellers")),
                price_change_h24=_f(change.get("h24")),
                pool_created_at=_parse_dt(attrs.get("pool_created_at")),
                url=url,
                source=source,
            )
        )
    return snapshots


def fetch_gecko_network(network: str, kind: str) -> list[TokenSnapshot]:
    url = (
        f"{GECKO_TERMINAL}/networks/{network}/{kind}_pools"
        "?include=base_token,quote_token,dex&page=1"
    )
    payload = _get_json(url)
    if not isinstance(payload, dict):
        return []
    return pools_to_snapshots(payload, chain=network, source=f"geckoterminal:{kind}")


def fetch_dexscreener_boosts() -> list[TokenSnapshot]:
    payload = _get_json(f"{DEXSCREENER}/token-boosts/top/v1")
    if not isinstance(payload, list):
        return []

    by_chain: dict[str, list[dict[str, Any]]] = {}
    for item in payload:
        chain = (item.get("chainId") or "").lower()
        address = item.get("tokenAddress")
        if chain and address:
            by_chain.setdefault(chain, []).append(item)

    snapshots: list[TokenSnapshot] = []
    for chain, items in by_chain.items():
        addresses = [i["tokenAddress"] for i in items[:20]]
        joined = ",".join(addresses)
        pairs_payload = _get_json(f"{DEXSCREENER}/tokens/v1/{chain}/{joined}")
        pairs = pairs_payload if isinstance(pairs_payload, list) else []
        desc_map = {i["tokenAddress"].lower(): i for i in items}
        best: dict[str, dict[str, Any]] = {}
        for pair in pairs:
            base = pair.get("baseToken") or {}
            addr = (base.get("address") or "").lower()
            if not addr:
                continue
            prev = best.get(addr)
            vol = ((pair.get("volume") or {}).get("h24")) or 0
            prev_vol = ((prev.get("volume") or {}).get("h24")) if prev else -1
            if prev is None or vol > prev_vol:
                best[addr] = pair
        for addr, pair in best.items():
            meta = desc_map.get(addr, {})
            base = pair.get("baseToken") or {}
            created = pair.get("pairCreatedAt")
            created_dt = None
            if isinstance(created, (int, float)):
                created_dt = datetime.fromtimestamp(created / 1000.0, tz=timezone.utc)
            liq = (pair.get("liquidity") or {}).get("usd")
            snapshots.append(
                TokenSnapshot(
                    chain=chain,
                    dex=(pair.get("dexId") or "unknown").lower(),
                    name=base.get("name") or base.get("symbol") or "unknown",
                    symbol=(base.get("symbol") or "?").lstrip("$"),
                    address=base.get("address") or "",
                    pair_address=pair.get("pairAddress") or "",
                    price_usd=_f(pair.get("priceUsd")),
                    fdv_usd=_f(pair.get("fdv")),
                    mcap_usd=_f(pair.get("marketCap")),
                    liquidity_usd=_f(liq),
                    volume_h24=_f((pair.get("volume") or {}).get("h24")),
                    price_change_h24=_f((pair.get("priceChange") or {}).get("h24")),
                    pool_created_at=created_dt,
                    url=pair.get("url") or meta.get("url") or "",
                    description=meta.get("description") or "",
                    source="dexscreener:boosts",
                )
            )
    return snapshots


def _meaningful(token: TokenSnapshot) -> bool:
    vol = token.volume_h24 or 0
    liq = token.liquidity_usd or 0
    size = token.size_usd or 0
    if vol < 25_000 and liq < 15_000:
        return False
    if size and size < 8_000:
        return False
    return True


def collect_snapshots(networks: tuple[str, ...] = DEFAULT_NETWORKS) -> list[TokenSnapshot]:
    jobs = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        jobs.append(pool.submit(fetch_dexscreener_boosts))
        for network in networks:
            jobs.append(pool.submit(fetch_gecko_network, network, "trending"))
            jobs.append(pool.submit(fetch_gecko_network, network, "new"))
        chunks: list[TokenSnapshot] = []
        for fut in as_completed(jobs):
            try:
                chunks.extend(fut.result())
            except Exception:
                continue

    unique: dict[tuple[str, str], TokenSnapshot] = {}
    for token in chunks:
        if not _meaningful(token):
            continue
        key = (token.chain, (token.address or token.pair_address).lower())
        prev = unique.get(key)
        if prev is None or (token.volume_h24 or 0) > (prev.volume_h24 or 0):
            unique[key] = token
    return list(unique.values())
