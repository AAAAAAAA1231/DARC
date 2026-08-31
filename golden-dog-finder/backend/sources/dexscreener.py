from __future__ import annotations

import httpx

from ..models import TokenSnapshot, TxWindow
from .httputil import gather_limited, get_json

DS = "https://api.dexscreener.com"


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def _tx(block: dict | None) -> TxWindow:
    block = block or {}
    return TxWindow(buys=int(block.get("buys") or 0), sells=int(block.get("sells") or 0))


def pair_to_snapshot(pair: dict, source: str = "dexscreener") -> TokenSnapshot | None:
    if not isinstance(pair, dict):
        return None
    base = pair.get("baseToken") or {}
    quote = pair.get("quoteToken") or {}
    addr = base.get("address")
    if not addr:
        return None
    qsym = (quote.get("symbol") or "").lower()
    if (base.get("symbol") or "").lower() in {"sol", "wsol", "weth", "eth", "wbnb", "usdc", "usdt"}:
        return None
    liq = (pair.get("liquidity") or {}).get("usd")
    vol = pair.get("volume") or {}
    chg = pair.get("priceChange") or {}
    tx = pair.get("txns") or {}
    info = pair.get("info") or {}
    socials = []
    for s in info.get("socials") or []:
        if isinstance(s, dict) and s.get("url"):
            socials.append({"type": s.get("type") or "social", "url": s["url"]})
    websites = [w.get("url") for w in (info.get("websites") or []) if isinstance(w, dict) and w.get("url")]
    boosts = pair.get("boosts") or {}
    mc = _num(pair.get("marketCap") or pair.get("fdv"))
    return TokenSnapshot(
        chain=pair.get("chainId") or "",
        address=addr,
        symbol=(base.get("symbol") or "")[:16],
        name=(base.get("name") or "")[:48],
        dex=pair.get("dexId") or "unknown",
        source=source,
        pair_address=pair.get("pairAddress"),
        price_usd=_num(pair.get("priceUsd")),
        market_cap_usd=mc,
        fdv_usd=_num(pair.get("fdv") or mc),
        liquidity_usd=_num(liq) if liq is not None else None,
        created_at_ms=int(pair.get("pairCreatedAt") or 0),
        volume_m5=_num(vol.get("m5")),
        volume_h1=_num(vol.get("h1")),
        volume_h6=_num(vol.get("h6")),
        volume_h24=_num(vol.get("h24")),
        change_m5=_num(chg.get("m5")),
        change_h1=_num(chg.get("h1")),
        change_h6=_num(chg.get("h6")),
        change_h24=_num(chg.get("h24")),
        tx_m5=_tx(tx.get("m5")),
        tx_h1=_tx(tx.get("h1")),
        image=(info.get("imageUrl") or None),
        websites=websites,
        socials=socials,
        boost_amount=int(boosts.get("active") or 0),
        has_profile=bool(info),
        url=pair.get("url"),
    )


async def fetch_discovery_lists(client: httpx.AsyncClient) -> list[dict]:
    payloads = await gather_limited(
        [
            get_json(client, f"{DS}/token-profiles/latest/v1"),
            get_json(client, f"{DS}/token-boosts/latest/v1"),
            get_json(client, f"{DS}/token-boosts/top/v1"),
            get_json(client, f"{DS}/community-takeovers/latest/v1"),
        ],
        limit=4,
    )
    items: list[dict] = []
    for payload in payloads:
        if isinstance(payload, list):
            items.extend([x for x in payload if isinstance(x, dict)])
    return items


async def fetch_pairs_for_tokens(
    client: httpx.AsyncClient, chain: str, addresses: list[str]
) -> list[TokenSnapshot]:
    snaps: list[TokenSnapshot] = []
    uniq = []
    seen = set()
    for a in addresses:
        key = a.lower()
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a)
    for i in range(0, len(uniq), 25):
        chunk = uniq[i : i + 25]
        payload = await get_json(client, f"{DS}/tokens/v1/{chain}/{','.join(chunk)}")
        rows = payload if isinstance(payload, list) else (payload or {}).get("pairs") if isinstance(payload, dict) else None
        if not rows:
            # fallback per-token
            for addr in chunk:
                one = await get_json(client, f"{DS}/latest/dex/tokens/{addr}")
                pairs = (one or {}).get("pairs") if isinstance(one, dict) else None
                if not pairs:
                    continue
                best = _best_pair(pairs, addr)
                snap = pair_to_snapshot(best, "dexscreener") if best else None
                if snap:
                    snaps.append(snap)
            continue
        grouped: dict[str, list[dict]] = {}
        for pair in rows:
            b = ((pair.get("baseToken") or {}).get("address") or "").lower()
            grouped.setdefault(b, []).append(pair)
        for addr in chunk:
            pairs = grouped.get(addr.lower()) or [p for p in rows if (p.get("baseToken") or {}).get("address", "").lower() == addr.lower()]
            best = _best_pair(pairs, addr)
            snap = pair_to_snapshot(best, "dexscreener") if best else None
            if snap:
                snaps.append(snap)
    return snaps


def _best_pair(pairs: list[dict], token: str) -> dict | None:
    token_l = token.lower()
    ranked = []
    for p in pairs:
        base = (p.get("baseToken") or {}).get("address", "").lower()
        if base != token_l:
            continue
        liq = _num((p.get("liquidity") or {}).get("usd"))
        vol = _num((p.get("volume") or {}).get("h1") or (p.get("volume") or {}).get("h24"))
        ranked.append((liq + vol, p))
    if not ranked:
        return pairs[0] if pairs else None
    ranked.sort(key=lambda x: x[0], reverse=True)
    return ranked[0][1]


def overlay_dex(dst: TokenSnapshot, src: TokenSnapshot) -> TokenSnapshot:
    if src.price_usd:
        dst.price_usd = src.price_usd
    if src.market_cap_usd:
        dst.market_cap_usd = src.market_cap_usd
        dst.fdv_usd = src.fdv_usd or src.market_cap_usd
    if src.liquidity_usd:
        dst.liquidity_usd = src.liquidity_usd
    if src.created_at_ms and (not dst.created_at_ms or src.created_at_ms < dst.created_at_ms):
        # keep earlier create time if we already have launch time
        if not dst.created_at_ms:
            dst.created_at_ms = src.created_at_ms
    if src.volume_h1:
        dst.volume_m5 = src.volume_m5
        dst.volume_h1 = src.volume_h1
        dst.volume_h6 = src.volume_h6
        dst.volume_h24 = src.volume_h24
    if src.tx_h1.buys or src.tx_m5.buys:
        if src.tx_m5.buyers == 0:
            src.tx_m5.buyers = dst.tx_m5.buyers
            src.tx_m5.sellers = src.tx_m5.sellers or dst.tx_m5.sellers
        if src.tx_h1.buyers == 0:
            src.tx_h1.buyers = dst.tx_h1.buyers
            src.tx_h1.sellers = src.tx_h1.sellers or dst.tx_h1.sellers
        dst.tx_m5 = src.tx_m5
        dst.tx_h1 = src.tx_h1
        if src.tx_m15.buys:
            dst.tx_m15 = src.tx_m15
    if src.change_h1 or src.change_m5:
        dst.change_m5 = src.change_m5
        dst.change_h1 = src.change_h1
        dst.change_h6 = src.change_h6
        dst.change_h24 = src.change_h24
    if src.image and not dst.image:
        dst.image = src.image
    if src.socials and not dst.socials:
        dst.socials = src.socials
    if src.websites and not dst.websites:
        dst.websites = src.websites
    if src.boost_amount:
        dst.boost_amount = src.boost_amount
        dst.has_profile = True
    if src.url and not dst.url:
        dst.url = src.url
    if src.pair_address:
        dst.pair_address = src.pair_address
        dst.dex = src.dex or dst.dex
    return dst
