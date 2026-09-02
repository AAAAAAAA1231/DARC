"""Launch / presale hunter. Class A/B/C from observable DexScreener + DefiLlama fields only."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import LaunchClass, ModuleName
from backend.core.identity import build_project_identity, is_evm_address
from backend.core.logging import get_logger
from backend.data_sources.dexscreener import DexScreenerProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import LaunchProject
from backend.services.projects import upsert_project
from backend.services.security import scan_token

logger = get_logger("launch")

SEARCH_TERMS = ("launch", "presale", "ido", "tge", "fair launch")


def classify(item: dict[str, Any]) -> LaunchClass:
    name = f"{item.get('baseToken', {}).get('name', '')} {item.get('description', '')}".lower()
    if any(k in name for k in ("blackrock", "a16z", "paradigm", "binance labs", "coinbase")):
        return LaunchClass.A
    if "btc" in name or "bitcoin" in name:
        return LaunchClass.B
    return LaunchClass.C


async def scan(session: Session) -> dict[str, Any]:
    dex = get_provider("dexscreener")
    assert isinstance(dex, DexScreenerProvider)
    collected: list[dict[str, Any]] = []
    source_notes = []
    for term in SEARCH_TERMS:
        env = await dex.search(term)
        source_notes.append({"term": term, "status": env.status.value, "error": env.error})
        if not env.ok:
            continue
        for pair in env.payload or []:
            if not isinstance(pair, dict):
                continue
            base = pair.get("baseToken") if isinstance(pair.get("baseToken"), dict) else {}
            addr = base.get("address")
            name = base.get("name") or base.get("symbol")
            if not name:
                continue
            chain = pair.get("chainId")
            identity = build_project_identity(
                name=name,
                chain=str(chain) if chain else None,
                contract=addr if is_evm_address(addr) else None,
            )
            launch_class = classify(pair)
            project = upsert_project(
                session,
                identity,
                module=ModuleName.LAUNCH.value,
                symbol=base.get("symbol"),
                extra={"pair": pair.get("pairAddress"), "url": pair.get("url")},
            )
            security = {"verdict": "UNKNOWN", "blocked": True}
            if chain and addr and is_evm_address(addr):
                security = await scan_token(session, project.project_id, str(chain), addr, base.get("symbol"))
            fields = {
                "name": name,
                "symbol": base.get("symbol"),
                "chain": chain,
                "contract": addr,
                "price_usd": pair.get("priceUsd"),
                "liquidity_usd": (pair.get("liquidity") or {}).get("usd") if isinstance(pair.get("liquidity"), dict) else None,
                "fdv": pair.get("fdv"),
                "pair_url": pair.get("url"),
                "launch_class": launch_class.value,
                "funding": "UNKNOWN",
                "team": "UNKNOWN",
                "community": "UNKNOWN",
                "tokenomics": "UNKNOWN",
                "unlock": "UNKNOWN",
                "class_note": "A = known-name keyword in pair metadata (not a verified VC table). B = BTC-related name. C = neither.",
                "security": security,
            }
            session.add(LaunchProject(project_id=project.project_id, launch_class=launch_class.value, category=term, fields=fields))
            collected.append({"project_id": project.project_id, "status": project.status, **fields})
            if len(collected) >= 40:
                break
        if len(collected) >= 40:
            break
    logger.info("launch_scan n=%s", len(collected))
    return {
        "ok": True,
        "projects": collected,
        "source_status": source_notes,
        "disclaimer": "Search hits from DexScreener public search. Funding/team/unlock remain UNKNOWN unless a dedicated source is wired. Class A is keyword-based, not a fake VC database.",
    }
