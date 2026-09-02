"""Contract / wallet / rug-risk scanner. Security is a hard gate, not a score that can be outvoted."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import DataQuality, SecurityVerdict, SourceStatus
from backend.core.logging import get_logger
from backend.data_sources.goplus import GoPlusProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import SecurityScan

logger = get_logger("security")

NATIVE_SYMBOLS = {"BTC", "ETH", "BNB", "SOL", "ADA", "XRP", "DOGE", "DOT", "ATOM", "NEAR", "AVAX", "TON", "TRX", "LTC", "BCH"}

_TRUE = {"1", "true", "yes"}


def _flag(value: Any) -> bool:
    if value is None:
        return False
    return str(value).strip().lower() in _TRUE


def _tax(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        raw = float(value)
    except (TypeError, ValueError):
        return None
    if raw > 1:
        raw = raw / 100.0
    return raw


def native_protocol_scan(project_id: str, symbol: str) -> dict[str, Any]:
    return {
        "project_id": project_id,
        "verdict": SecurityVerdict.NATIVE_PROTOCOL.value,
        "score": 80.0,
        "blocked": False,
        "findings": {
            "kind": "native_protocol",
            "symbol": symbol,
            "note": "No EVM/token contract to scan. Native L1/L0 asset — not equivalent to SAFE token.",
        },
        "source": "heuristic",
        "data_quality": DataQuality.OK.value,
    }


def evaluate_goplus(payload: dict[str, Any]) -> dict[str, Any]:
    findings: dict[str, Any] = {
        "mint": _flag(payload.get("is_mintable")),
        "honeypot": _flag(payload.get("is_honeypot")),
        "cannot_sell_all": _flag(payload.get("cannot_sell_all")),
        "cannot_buy": _flag(payload.get("cannot_buy")),
        "hidden_owner": _flag(payload.get("hidden_owner")),
        "proxy": _flag(payload.get("is_proxy")),
        "open_source": _flag(payload.get("is_open_source")),
        "blacklist": _flag(payload.get("is_blacklisted")),
        "whitelist": _flag(payload.get("is_whitelisted")),
        "pause": _flag(payload.get("can_pause")),
        "owner_change_balance": _flag(payload.get("owner_change_balance")),
        "take_back_ownership": _flag(payload.get("can_take_back_ownership")),
        "buy_tax": _tax(payload.get("buy_tax")),
        "sell_tax": _tax(payload.get("sell_tax")),
        "holder_count": payload.get("holder_count"),
        "owner_address": payload.get("owner_address"),
        "creator_address": payload.get("creator_address"),
        "is_in_dex": _flag(payload.get("is_in_dex")),
        "lp_holders": payload.get("lp_holders") or [],
        "holders": payload.get("holder_top") or [],
        "anti_whale": _flag(payload.get("is_anti_whale")),
        "trading_cooldown": _flag(payload.get("trading_cooldown")),
    }
    lp_unlocked = False
    for lp in findings["lp_holders"]:
        if isinstance(lp, dict) and str(lp.get("is_locked", "0")) in {"0", "false", "False"} and float(lp.get("percent") or 0) > 10:
            lp_unlocked = True
            break
    findings["lp_unlocked_risk"] = lp_unlocked

    malicious = findings["honeypot"] or findings["cannot_sell_all"] or findings["cannot_buy"]
    severe_backdoor = findings["hidden_owner"] and findings["mint"]
    owner_dump = findings["owner_change_balance"] or findings["take_back_ownership"]
    high_tax = (findings["sell_tax"] or 0) >= 0.10 or (findings["buy_tax"] or 0) >= 0.10

    if malicious or severe_backdoor:
        verdict = SecurityVerdict.MALICIOUS
        score = 5.0
    elif not findings["open_source"] or owner_dump or lp_unlocked or high_tax:
        verdict = SecurityVerdict.HIGH_RISK
        score = 25.0
    elif findings["mint"] or findings["proxy"] or findings["blacklist"] or findings["pause"]:
        verdict = SecurityVerdict.MEDIUM_RISK
        score = 45.0
    elif findings["anti_whale"] or findings["trading_cooldown"] or (findings["sell_tax"] or 0) > 0:
        verdict = SecurityVerdict.LOW_RISK
        score = 70.0
    else:
        verdict = SecurityVerdict.SAFE
        score = 88.0

    blocked = verdict in {SecurityVerdict.MALICIOUS, SecurityVerdict.HIGH_RISK, SecurityVerdict.UNKNOWN}
    return {
        "verdict": verdict.value,
        "score": score,
        "blocked": blocked,
        "findings": findings,
    }


async def scan_token(session: Session, project_id: str, chain: str | None, contract: str | None, symbol: str | None) -> dict[str, Any]:
    if not contract or not chain:
        if symbol and symbol.upper() in NATIVE_SYMBOLS:
            result = native_protocol_scan(project_id, symbol.upper())
        else:
            result = {
                "project_id": project_id,
                "verdict": SecurityVerdict.UNKNOWN.value,
                "score": None,
                "blocked": True,
                "findings": {"reason": "no contract/chain and not a known native protocol asset"},
                "source": "none",
                "data_quality": DataQuality.MISSING.value,
            }
        _persist(session, project_id, chain, contract, result)
        return result

    provider = get_provider("goplus")
    assert isinstance(provider, GoPlusProvider)
    env = await provider.token_security(chain, contract)
    if env.status != SourceStatus.OK or not env.payload:
        result = {
            "project_id": project_id,
            "verdict": SecurityVerdict.UNKNOWN.value,
            "score": None,
            "blocked": True,
            "findings": {"reason": env.error or "security payload empty", "source_status": env.status.value},
            "source": "goplus",
            "data_quality": env.data_quality.value,
        }
        _persist(session, project_id, chain, contract, result)
        logger.warning("security_unknown project=%s status=%s", project_id, env.status.value)
        return result

    evaluated = evaluate_goplus(env.payload)
    result = {
        "project_id": project_id,
        "verdict": evaluated["verdict"],
        "score": evaluated["score"],
        "blocked": evaluated["blocked"] or evaluated["verdict"] == SecurityVerdict.UNKNOWN.value,
        "findings": evaluated["findings"],
        "source": "goplus",
        "data_quality": env.data_quality.value,
        "raw_keys": sorted(env.payload.keys()),
    }
    # UNKNOWN is never SAFE. GoPlus success still maps to a concrete verdict above.
    if result["verdict"] == SecurityVerdict.UNKNOWN.value:
        result["blocked"] = True
    if result["verdict"] in {SecurityVerdict.MALICIOUS.value, SecurityVerdict.HIGH_RISK.value}:
        result["blocked"] = True
    _persist(session, project_id, chain, contract, result)
    return result


def _persist(session: Session, project_id: str, chain: str | None, contract: str | None, result: dict[str, Any]) -> None:
    session.add(
        SecurityScan(
            project_id=project_id,
            chain=chain,
            contract=contract,
            verdict=result["verdict"],
            score=result.get("score"),
            findings=result.get("findings") or {},
            source=result.get("source") or "unknown",
            data_quality=result.get("data_quality") or DataQuality.MISSING.value,
        )
    )


def can_enter_recommendation_pool(verdict: str) -> bool:
    return verdict in {
        SecurityVerdict.SAFE.value,
        SecurityVerdict.LOW_RISK.value,
        SecurityVerdict.MEDIUM_RISK.value,
        SecurityVerdict.NATIVE_PROTOCOL.value,
    }
