from __future__ import annotations

import httpx

from ..models import PumpState, TokenSnapshot
from .httputil import get_json

PUMP_API = "https://frontend-api-v3.pump.fun/coins"
SOL = "solana"


def _num(v) -> float:
    try:
        return float(v or 0)
    except (TypeError, ValueError):
        return 0.0


def coin_to_snapshot(coin: dict) -> TokenSnapshot | None:
    if not isinstance(coin, dict):
        return None
    mint = coin.get("mint")
    if not mint:
        return None
    if coin.get("is_banned"):
        return None
    mc = _num(coin.get("market_cap_usd") or coin.get("usd_market_cap"))
    created = int(coin.get("created_timestamp") or 0)
    real_sol = _num(coin.get("real_sol_reserves") or coin.get("real_quote_reserves")) / 1e9
    image = coin.get("image_uri") or coin.get("profile_image")
    socials = []
    twitter = coin.get("twitter")
    telegram = coin.get("telegram")
    website = coin.get("website")
    if twitter:
        socials.append({"type": "twitter", "url": twitter})
    if telegram:
        socials.append({"type": "telegram", "url": telegram})
    websites = [website] if website else []
    supply = _num(coin.get("total_supply")) or 1_000_000_000_000_000
    # pump stores 1B tokens at 6 decimals → 1e15 raw
    price = _num(coin.get("price_usd")) or (mc / max(supply / 10 ** int(coin.get("base_decimals") or 6), 1) if mc else 0)
    return TokenSnapshot(
        chain=SOL,
        address=mint,
        symbol=(coin.get("symbol") or "")[:16],
        name=(coin.get("name") or "")[:48],
        dex="pumpfun" if not coin.get("complete") else "pumpswap",
        source="pump.fun",
        pair_address=coin.get("bonding_curve") or coin.get("pool_address"),
        price_usd=price,
        market_cap_usd=mc,
        fdv_usd=mc,
        liquidity_usd=real_sol * 103.0 if not coin.get("complete") and real_sol else None,
        created_at_ms=created if created > 10_000_000_000 else created * 1000,
        image=image,
        websites=websites,
        socials=socials,
        url=f"https://pump.fun/coin/{mint}",
        pump=PumpState(
            complete=bool(coin.get("complete")),
            real_sol=real_sol,
            reply_count=int(coin.get("reply_count") or 0),
            livestream=bool(coin.get("is_currently_live")),
            nsfw=bool(coin.get("nsfw")),
            bonding_curve=coin.get("bonding_curve"),
            creator=coin.get("creator"),
            ath_mc=0.0,
        ),
    )


def _fix_ath(coin: dict, snap: TokenSnapshot) -> None:
    """ath_market_cap on pump API is often in SOL; convert when possible."""
    if not snap.pump:
        return
    ath = _num(coin.get("ath_market_cap"))
    mc_sol = _num(coin.get("market_cap"))
    mc_usd = snap.market_cap_usd
    if ath and mc_sol and mc_usd:
        snap.pump.ath_mc = ath * (mc_usd / mc_sol)
    elif ath and ath > 1000:
        snap.pump.ath_mc = ath


async def fetch_pump(client: httpx.AsyncClient) -> list[TokenSnapshot]:
    sorts = ("created_timestamp", "last_trade_timestamp", "reply_count")
    out: dict[str, TokenSnapshot] = {}
    for sort in sorts:
        payload = await get_json(
            client,
            PUMP_API,
            params={
                "offset": 0,
                "limit": 50,
                "sort": sort,
                "order": "DESC",
                "includeNsfw": "false",
            },
            browser=True,
        )
        if not isinstance(payload, list):
            continue
        for coin in payload:
            snap = coin_to_snapshot(coin)
            if not snap:
                continue
            _fix_ath(coin, snap)
            prev = out.get(snap.key)
            if prev and prev.pump and snap.pump:
                snap.pump.reply_count = max(prev.pump.reply_count, snap.pump.reply_count)
                snap.volume_h1 = max(prev.volume_h1, snap.volume_h1)
            out[snap.key] = snap
    return list(out.values())
