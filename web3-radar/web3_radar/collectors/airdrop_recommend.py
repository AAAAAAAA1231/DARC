from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from web3_radar.collectors.airdrop import scan_airdrops
from web3_radar.engine.airdrop_rank import load_history, load_watchlist, merge_candidates, rank_candidates


async def recommend_airdrops(min_funding_usd: float = 10_000_000) -> dict[str, Any]:
    errors: list[str] = []
    live: list[dict[str, Any]] = []
    try:
        payload = await scan_airdrops(min_funding_usd=min_funding_usd)
        live = list(payload.get("items") or [])
        errors.extend(payload.get("errors") or [])
    except Exception as exc:
        errors.append(f"live: {exc}")
    history = load_history()
    watch = load_watchlist()
    merged = merge_candidates(live, watch)
    ranked = rank_candidates(merged, history)
    recs = [r for r in ranked if r.get("recommend")]
    others = [r for r in ranked if not r.get("recommend")]
    ordered = recs + others
    for i, row in enumerate(ordered, start=1):
        row["rank"] = i
    return {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(ordered),
        "recommend_count": len(recs),
        "model": "institutions 25 + confirmed 25 + difficulty 20 + expected 20 + history adj",
        "disclaimer": "按机构、是否明确空投、参与难度、预计总金额打分，再用历史空投对照修正。不是参与建议。",
        "items": ordered[:80],
        "errors": errors,
    }
