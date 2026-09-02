"""Airdrop hunter from DefiLlama protocols that have no token or nascent token. UNKNOWN stays UNKNOWN."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import ModuleName
from backend.core.identity import build_project_identity
from backend.core.logging import get_logger
from backend.data_sources.defillama import DefiLlamaProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import AirdropProject
from backend.services.projects import upsert_project

logger = get_logger("airdrop")


def _unknown_money(value: Any) -> str:
    if value in (None, "", 0, "0"):
        return "UNKNOWN"
    return str(value)


async def scan(session: Session, limit: int = 40) -> dict[str, Any]:
    llama = get_provider("defillama")
    assert isinstance(llama, DefiLlamaProvider)
    env = await llama.protocols()
    if not env.ok:
        return {"ok": False, "source_status": env.as_dict(), "projects": []}
    out = []
    for proto in env.payload[:200]:
        symbol = proto.get("symbol")
        tvl = proto.get("tvl") or 0
        if symbol and symbol not in {"-", "N/A"}:
            continue
        if tvl < 1_000_000:
            continue
        identity = build_project_identity(
            name=proto["name"],
            website=proto.get("url"),
            twitter=proto.get("twitter"),
        )
        project = upsert_project(
            session,
            identity,
            module=ModuleName.AIRDROP.value,
            extra={"defillama": proto.get("slug"), "tvl": tvl},
        )
        fields = {
            "project": proto["name"],
            "chain": proto.get("chain") or "UNKNOWN",
            "funding": "UNKNOWN",
            "estimated_valuation": "UNKNOWN",
            "participation_cost": "UNKNOWN",
            "expected_value_range": "UNKNOWN",
            "expected_roi": "UNKNOWN",
            "risk": "UNKNOWN" if not proto.get("audits") else "MEDIUM",
            "difficulty": "UNKNOWN",
            "time_cost": "UNKNOWN",
            "tvl": tvl,
            "tvl_change_1d": proto.get("change_1d"),
            "category": proto.get("category"),
            "url": proto.get("url"),
            "twitter": proto.get("twitter"),
            "token_probability": "UNKNOWN",
            "recommended": False,
        }
        session.add(
            AirdropProject(
                project_id=project.project_id,
                chain=fields["chain"] if fields["chain"] != "UNKNOWN" else None,
                funding=fields["funding"],
                estimated_valuation=fields["estimated_valuation"],
                participation_cost=fields["participation_cost"],
                expected_value_range=fields["expected_value_range"],
                expected_roi=fields["expected_roi"],
                risk=fields["risk"],
                difficulty=fields["difficulty"],
                time_cost=fields["time_cost"],
                recommended=False,
                fields=fields,
            )
        )
        out.append({"project_id": project.project_id, "status": project.status, **fields})
        if len(out) >= limit:
            break
    logger.info("airdrop_scan n=%s", len(out))
    return {
        "ok": True,
        "projects": out,
        "source_status": {"defillama": {"status": env.status.value, "n": len(env.payload or [])}},
        "disclaimer": "Candidates are protocols with TVL and no listed token symbol on DefiLlama. Funding, valuation, and expected return are UNKNOWN unless a dedicated funding provider is configured. Nothing here is fabricated.",
    }
