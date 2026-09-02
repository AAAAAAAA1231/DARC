"""50X Opportunity Radar: live scan + security gate + multi-factor score + unified identity."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import ModuleName, NarrativeTag
from backend.core.identity import build_project_identity
from backend.core.logging import get_logger
from backend.data_sources.coingecko import CoinGeckoProvider
from backend.data_sources.dexscreener import DexScreenerProvider
from backend.data_sources.goplus import CHAIN_ID
from backend.data_sources.registry import get_provider
from backend.services.model_center import ensure_default_version
from backend.services.projects import record_score, upsert_project, visible_filter
from backend.services.scoring import (
    classify_narrative,
    combine_50x,
    score_historical_similarity,
    score_holders,
    score_liquidity,
    score_market_structure,
    score_narrative,
    score_social,
    score_volume,
)
from backend.services.security import can_enter_recommendation_pool, scan_token
from backend.database.orm import Project, SecurityScan

logger = get_logger("radar")

CHAIN_FROM_PLATFORM = {
    "ethereum": "ethereum",
    "binance-smart-chain": "bsc",
    "polygon-pos": "polygon",
    "arbitrum-one": "arbitrum",
    "optimistic-ethereum": "optimism",
    "base": "base",
    "avalanche": "avalanche",
}


def _pick_chain_contract(platforms: dict[str, str] | None) -> tuple[str | None, str | None]:
    if not platforms:
        return None, None
    for platform, chain in CHAIN_FROM_PLATFORM.items():
        addr = platforms.get(platform)
        if addr:
            return chain, addr
    for platform, addr in platforms.items():
        if addr and platform.lower() in CHAIN_ID:
            return platform.lower(), addr
    return None, None


async def scan_radar(session: Session, limit: int = 40) -> dict[str, Any]:
    ensure_default_version(session, "RADAR")
    gecko = get_provider("coingecko")
    assert isinstance(gecko, CoinGeckoProvider)
    markets = await gecko.markets(per_page=min(limit, 100), page=1)
    detail_budget = min(8, limit)
    source_status = {"coingecko": markets.as_dict() | {"payload": f"{len(markets.payload or [])} rows"}}
    if not markets.ok:
        return {
            "ok": False,
            "source_status": {"coingecko": markets.as_dict()},
            "candidates": [],
            "recommended": [],
            "disclaimer": "实时行情不可用。不会展示编造的排名。",
        }

    dex: DexScreenerProvider = get_provider("dexscreener")  # type: ignore[assignment]
    results: list[dict[str, Any]] = []
    for idx, coin in enumerate(markets.payload[:limit]):
        detail_env = None
        detail: dict[str, Any] = {}
        if idx < detail_budget:
            detail_env = await gecko.coin_detail(coin["id"])
            detail = detail_env.payload if detail_env.ok else {}
        platforms = (detail or {}).get("platforms") if isinstance(detail, dict) else {}
        chain, contract = _pick_chain_contract(platforms)
        identity = build_project_identity(
            name=coin["name"],
            chain=chain,
            contract=contract,
            website=(detail or {}).get("homepage") if isinstance(detail, dict) else None,
            twitter=(detail or {}).get("twitter") if isinstance(detail, dict) else None,
        )
        narrative = classify_narrative(
            (detail or {}).get("categories") if isinstance(detail, dict) else coin.get("categories"),
            (detail or {}).get("description") if isinstance(detail, dict) else None,
        )
        project = upsert_project(
            session,
            identity,
            module=ModuleName.RADAR_50X.value,
            symbol=coin["symbol"],
            narrative=narrative.value,
            extra={"coingecko_id": coin["id"]},
        )
        security = await scan_token(session, project.project_id, chain, contract, coin["symbol"])
        liq = None
        if chain and contract:
            pairs_env = await dex.token_pairs(chain, contract)
            if pairs_env.ok and pairs_env.payload:
                liqs = [p.get("liquidity_usd") for p in pairs_env.payload if p.get("liquidity_usd") is not None]
                liq = max(liqs) if liqs else None

        community = (detail or {}).get("community") if isinstance(detail, dict) else None
        developer = (detail or {}).get("developer") if isinstance(detail, dict) else None
        holders = None
        if security.get("findings") and isinstance(security["findings"], dict):
            holders = security["findings"].get("holder_count")

        parts = {
            "market_structure": score_market_structure(
                coin.get("market_cap"), coin.get("fully_diluted_valuation"), coin.get("circulating_supply"), coin.get("total_supply")
            ),
            "liquidity": score_liquidity(liq),
            "volume": score_volume(coin.get("total_volume"), coin.get("market_cap"), coin.get("price_change_percentage_24h")),
            "holders": score_holders(holders),
            "smart_money": (None, "UNKNOWN"),
            "whale": (None, "UNKNOWN"),
            "fund_flow": (None, "UNKNOWN"),
            "narrative": score_narrative(narrative),
            "social": score_social(community, developer),
            "vc": (None, "UNKNOWN"),
            "team": (None, "UNKNOWN"),
            "tokenomics": score_market_structure(
                coin.get("market_cap"), coin.get("fully_diluted_valuation"), coin.get("circulating_supply"), coin.get("total_supply")
            ),
            "ecosystem": (None, "UNKNOWN"),
            "onchain": (None, "UNKNOWN"),
            "market_cycle": (None, "UNKNOWN"),
            "historical_similarity": score_historical_similarity(
                coin.get("ath"), coin.get("atl"), coin.get("current_price"), coin.get("market_cap")
            ),
        }
        combined = combine_50x(parts, security.get("score"), security["verdict"])
        eligible = can_enter_recommendation_pool(security["verdict"]) and combined["score_50x"] is not None
        explanation = {
            "why": "Multi-factor structure vs live market snapshot. Security is a hard gate.",
            "for": [k for k, v in parts.items() if v[0] is not None and v[0] >= 60],
            "against": [k for k, v in parts.items() if v[0] is not None and v[0] < 45] + combined["unknown_factors"],
            "risks": [security["verdict"]],
            "invalidation": "出现恶意/高风险/未知的安全结论，或流动性/成交质量崩溃。",
            "not_a_certainty": True,
        }
        record_score(
            session,
            project.project_id,
            ModuleName.RADAR_50X.value,
            "radar_live",
            {**combined, "security_verdict": security["verdict"]},
            "FOLLOW" if eligible and (combined["score_50x"] or 0) >= 65 else "REJECT" if not eligible else "WATCH",
            explanation,
        )
        results.append(
            {
                "project_id": project.project_id,
                "name": project.name,
                "symbol": coin["symbol"],
                "chain": chain,
                "contract": contract,
                "price": coin.get("current_price"),
                "market_cap": coin.get("market_cap"),
                "volume_24h": coin.get("total_volume"),
                "narrative": narrative.value,
                "status": project.status,
                "hidden": project.hidden,
                "security": security,
                "scores": combined,
                "eligible_for_pool": eligible,
                "sources": ["50X"],
                "data_quality": {
                    "coingecko_detail": detail_env.data_quality.value if detail_env else "skipped_rate_limit_budget",
                    "security": security.get("data_quality"),
                },
                "explanation": explanation,
            }
        )

    visible_ids = {p.project_id for p in visible_filter(session.query(Project)).all()}
    visible = [r for r in results if r["project_id"] in visible_ids]
    recommended = sorted(
        [r for r in visible if r["eligible_for_pool"]],
        key=lambda r: r["scores"]["score_50x"] or 0,
        reverse=True,
    )
    logger.info("radar_scan coins=%s recommended=%s", len(results), len(recommended))
    return {
        "ok": True,
        "source_status": source_status,
        "disclaimer": "基于实时数据的统计排名。不是10倍/50倍承诺。安全状态为未知的永不入池。",
        "candidates": visible,
        "recommended": recommended[:20],
        "top10": recommended[:10],
        "excluded_security": [r for r in results if not r["eligible_for_pool"]],
    }


def latest_scans(session: Session, limit: int = 20) -> list[dict[str, Any]]:
    rows = session.query(SecurityScan).order_by(SecurityScan.created_at.desc()).limit(limit).all()
    return [
        {
            "project_id": r.project_id,
            "verdict": r.verdict,
            "score": float(r.score) if r.score is not None else None,
            "source": r.source,
            "at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def latest_pool(session: Session) -> dict[str, Any]:
    from backend.services.dashboard import _latest_radar

    items = _latest_radar(session)
    recommended = []
    for row in items:
        recommended.append(
            {
                "project_id": row["project_id"],
                "name": row["name"],
                "symbol": row["symbol"],
                "scores": {"score_50x": row.get("score"), "grade": row.get("grade")},
                "security": {"verdict": row.get("security")},
                "eligible_for_pool": True,
                "market_cap": "UNKNOWN",
                "signal": row.get("signal"),
            }
        )
    return {
        "ok": True,
        "from_cache": True,
        "recommended": recommended,
        "candidates": [],
        "disclaimer": "上次保存的、已通过安全门槛的五十倍分数。点击扫描可重新跑 CoinGecko + GoPlus。",
    }
