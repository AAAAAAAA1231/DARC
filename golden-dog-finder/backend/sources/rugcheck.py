from __future__ import annotations

import httpx

from ..models import SecurityState, TokenSnapshot
from .httputil import get_json

RUGCHECK = "https://api.rugcheck.xyz/v1/tokens"


def _pct_top_non_curve(holders: list[dict], pump_curve: str | None) -> float | None:
    if not holders:
        return None
    curve = (pump_curve or "").lower()
    for h in holders:
        owner = (h.get("owner") or h.get("address") or "").lower()
        if curve and owner == curve:
            continue
        # skip known pool-ish large first account if percent insane and we have a curve
        pct = h.get("pct")
        try:
            return float(pct)
        except (TypeError, ValueError):
            return None
    try:
        return float(holders[0].get("pct") or 0)
    except (TypeError, ValueError):
        return None


async def enrich_security(client: httpx.AsyncClient, token: TokenSnapshot) -> SecurityState | None:
    if token.chain != "solana":
        return None
    data = await get_json(client, f"{RUGCHECK}/{token.address}/report")
    if not isinstance(data, dict) or data.get("error"):
        summary = await get_json(client, f"{RUGCHECK}/{token.address}/report/summary")
        if not isinstance(summary, dict):
            return None
        data = summary
    risks = []
    for r in data.get("risks") or []:
        if isinstance(r, dict):
            name = r.get("name") or r.get("description") or ""
            if name:
                risks.append(str(name))
        elif r:
            risks.append(str(r))
    holders = data.get("topHolders") or []
    curve = token.pump.bonding_curve if token.pump else None
    return SecurityState(
        rugged=bool(data.get("rugged")),
        score=data.get("score") if isinstance(data.get("score"), int) else None,
        score_normalised=data.get("score_normalised")
        if isinstance(data.get("score_normalised"), int)
        else None,
        mint_authority=data.get("mintAuthority"),
        freeze_authority=data.get("freezeAuthority"),
        lp_locked_pct=_lp_lock(data),
        holders=data.get("totalHolders") if isinstance(data.get("totalHolders"), int) else None,
        top_holder_pct=_pct_top_non_curve(holders, curve),
        insider_networks=data.get("graphInsidersDetected")
        if isinstance(data.get("graphInsidersDetected"), int)
        else None,
        risks=risks[:8],
    )


def _lp_lock(data: dict) -> float | None:
    markets = data.get("markets") or []
    pcts = []
    for m in markets:
        if not isinstance(m, dict):
            continue
        for key in ("lpLockedPct", "lp_locked_pct"):
            if m.get(key) is not None:
                try:
                    pcts.append(float(m[key]))
                except (TypeError, ValueError):
                    pass
    if pcts:
        return max(pcts)
    if data.get("lpLockedPct") is not None:
        try:
            return float(data["lpLockedPct"])
        except (TypeError, ValueError):
            return None
    return None
