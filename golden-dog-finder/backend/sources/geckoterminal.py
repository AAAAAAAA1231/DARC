from __future__ import annotations

from datetime import datetime, timezone

import httpx

from ..models import TokenSnapshot, TxWindow
from .httputil import gather_limited, get_json

GT = "https://api.geckoterminal.com/api/v2"
NETWORKS = ("solana", "base", "bsc")
QUOTE_OK = {
    "sol",
    "wsol",
    "eth",
    "weth",
    "bnb",
    "wbnb",
    "usdc",
    "usdt",
    "usd1",
}


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _iso_ms(value: str | None) -> int:
    if not value:
        return 0
    try:
        cleaned = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return 0


def _tx(block: dict | None) -> TxWindow:
    block = block or {}
    return TxWindow(
        buys=int(block.get("buys") or 0),
        sells=int(block.get("sells") or 0),
        buyers=int(block.get("buyers") or 0),
        sellers=int(block.get("sellers") or 0),
    )


def _included_map(payload: dict) -> dict[str, dict]:
    out = {}
    for item in payload.get("included") or []:
        if item.get("id"):
            out[item["id"]] = item.get("attributes") or {}
    return out


def _token_addr(rel_id: str | None) -> str:
    if not rel_id:
        return ""
    # ids look like "solana_So1111..."
    if "_" in rel_id:
        return rel_id.split("_", 1)[1]
    return rel_id


def pool_to_snapshot(pool: dict, included: dict[str, dict], source: str) -> TokenSnapshot | None:
    attrs = pool.get("attributes") or {}
    rel = pool.get("relationships") or {}
    base_rel = ((rel.get("base_token") or {}).get("data") or {})
    quote_rel = ((rel.get("quote_token") or {}).get("data") or {})
    dex_rel = ((rel.get("dex") or {}).get("data") or {})
    network = (pool.get("id") or "solana").split("_", 1)[0]
    base_id = base_rel.get("id")
    quote_id = quote_rel.get("id")
    base = included.get(base_id or "", {})
    quote = included.get(quote_id or "", {})
    name = attrs.get("name") or ""
    symbol = (base.get("symbol") or name.split("/")[0]).strip()
    quote_sym = (quote.get("symbol") or (name.split("/")[-1] if "/" in name else "")).strip()
    if symbol.lower() in {"sol", "wsol", "weth", "eth", "wbnb", "bnb", "usdc", "usdt"}:
        return None
    if quote_sym and quote_sym.lower() not in QUOTE_OK:
        return None
    fdv = _num(attrs.get("fdv_usd"))
    mc = _num(attrs.get("market_cap_usd")) or fdv
    liq = attrs.get("reserve_in_usd")
    liq_n = _num(liq) if liq is not None else None
    if liq_n is not None and liq_n < 0:
        return None
    vol = attrs.get("volume_usd") or {}
    chg = attrs.get("price_change_percentage") or {}
    tx = attrs.get("transactions") or {}
    addr = _token_addr(base_id) or (base.get("address") or "")
    if not addr:
        return None
    dex = dex_rel.get("id") or "unknown"
    pair = attrs.get("address")
    chain_path = network
    url = f"https://www.geckoterminal.com/{chain_path}/pools/{pair}" if pair else None
    return TokenSnapshot(
        chain=network,
        address=addr,
        symbol=symbol[:16],
        name=(base.get("name") or symbol)[:48],
        dex=dex,
        source=source,
        pair_address=pair,
        price_usd=_num(attrs.get("base_token_price_usd")),
        market_cap_usd=mc,
        fdv_usd=fdv,
        liquidity_usd=liq_n,
        created_at_ms=_iso_ms(attrs.get("pool_created_at")),
        volume_m5=_num(vol.get("m5")),
        volume_h1=_num(vol.get("h1")),
        volume_h6=_num(vol.get("h6")),
        volume_h24=_num(vol.get("h24")),
        change_m5=_num(chg.get("m5")),
        change_h1=_num(chg.get("h1")),
        change_h6=_num(chg.get("h6")),
        change_h24=_num(chg.get("h24")),
        tx_m5=_tx(tx.get("m5")),
        tx_m15=_tx(tx.get("m15")),
        tx_h1=_tx(tx.get("h1")),
        image=base.get("image_url"),
        url=url,
    )


async def fetch_geckoterminal(client: httpx.AsyncClient) -> list[TokenSnapshot]:
    out: dict[str, TokenSnapshot] = {}
    jobs: list[tuple[str, str]] = []
    for net in NETWORKS:
        jobs.append((f"{GT}/networks/{net}/new_pools", "gt-new"))
        jobs.append((f"{GT}/networks/{net}/trending_pools", "gt-trend"))
    jobs.append((f"{GT}/networks/new_pools", "gt-global-new"))

    payloads = await gather_limited(
        [
            get_json(
                client,
                url,
                params={"include": "base_token,quote_token,dex", "page": 1},
                headers={"Accept": "application/json;version=20230302"},
            )
            for url, _ in jobs
        ],
        limit=4,
    )
    for payload, (_, source) in zip(payloads, jobs):
        if not isinstance(payload, dict):
            continue
        included = _included_map(payload)
        for pool in payload.get("data") or []:
            snap = pool_to_snapshot(pool, included, source)
            if not snap:
                continue
            prev = out.get(snap.key)
            if prev:
                snap = _merge(prev, snap)
            out[snap.key] = snap
    return list(out.values())


def _merge(a: TokenSnapshot, b: TokenSnapshot) -> TokenSnapshot:
    """Prefer the snapshot with richer flow / liquidity."""
    pick = b if (b.volume_h1, b.tx_h1.buyers) > (a.volume_h1, a.tx_h1.buyers) else a
    other = a if pick is b else b
    if not pick.liquidity_usd and other.liquidity_usd:
        pick.liquidity_usd = other.liquidity_usd
    if not pick.image and other.image:
        pick.image = other.image
    if other.pump and not pick.pump:
        pick.pump = other.pump
    return pick
