"""GoPlus token security. Public endpoint; app key optional."""

from __future__ import annotations

from typing import Any

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_str, require_mapping
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient

CHAIN_ID = {
    "ethereum": "1",
    "eth": "1",
    "bsc": "56",
    "bnb": "56",
    "polygon": "137",
    "matic": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "base": "8453",
    "avalanche": "43114",
    "avax": "43114",
    "fantom": "250",
    "cronos": "25",
    "gnosis": "100",
    "linea": "59144",
    "scroll": "534352",
    "zksync": "324",
    "mantle": "5000",
    "blast": "81457",
}


class GoPlusProvider(DataProvider):
    name = "goplus"

    def __init__(self) -> None:
        settings = get_settings()
        cfg = settings.yaml_config.get("providers", {}).get("goplus", {})
        self.base = str(cfg.get("base", "https://api.gopluslabs.io/api/v1")).rstrip("/")
        headers: dict[str, str] = {}
        if settings.goplus_app_key:
            headers["Authorization"] = settings.goplus_app_key
        self.http = HttpClient(self.name, float(cfg.get("timeout_sec", 20)), headers)

    async def health(self) -> QualityEnvelope:
        return await self.http.get_json(f"{self.base}/supported_chains?name=token_security")

    def chain_id(self, chain: str) -> str | None:
        return CHAIN_ID.get((chain or "").strip().lower())

    async def token_security(self, chain: str, contract: str) -> QualityEnvelope:
        chain_id = self.chain_id(chain)
        if not chain_id:
            return envelope(
                self.name,
                status=SourceStatus.SCHEMA_ERROR,
                data_quality=DataQuality.INVALID,
                error=f"unsupported chain for GoPlus: {chain}",
            )
        raw = await self.http.get_json(
            f"{self.base}/token_security/{chain_id}",
            params={"contract_addresses": contract.lower()},
            expect=dict,
        )
        if not raw.ok:
            return raw
        try:
            body = require_mapping(raw.payload, "goplus")
        except ValueError as exc:
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error=str(exc))
        result = body.get("result")
        if not isinstance(result, dict) or not result:
            return envelope(
                self.name,
                status=SourceStatus.OK,
                payload=None,
                data_quality=DataQuality.MISSING,
                confidence=0.0,
                error="empty security result",
            )
        key = next(iter(result))
        token = result.get(key)
        if not isinstance(token, dict):
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error="token payload not object")
        parsed: dict[str, Any] = {
            "contract": optional_str(token, "contract") or contract.lower(),
            "chain_id": chain_id,
            "token_name": optional_str(token, "token_name"),
            "token_symbol": optional_str(token, "token_symbol"),
            "is_open_source": optional_str(token, "is_open_source"),
            "is_proxy": optional_str(token, "is_proxy"),
            "is_mintable": optional_str(token, "is_mintable"),
            "can_take_back_ownership": optional_str(token, "can_take_back_ownership"),
            "owner_change_balance": optional_str(token, "owner_change_balance"),
            "hidden_owner": optional_str(token, "hidden_owner"),
            "selfdestruct": optional_str(token, "selfdestruct"),
            "external_call": optional_str(token, "external_call"),
            "gas_abuse": optional_str(token, "gas_abuse"),
            "buy_tax": optional_str(token, "buy_tax"),
            "sell_tax": optional_str(token, "sell_tax"),
            "transfer_tax": optional_str(token, "transfer_pausable"),
            "is_honeypot": optional_str(token, "is_honeypot"),
            "honeypot_with_same_creator": optional_str(token, "honeypot_with_same_creator"),
            "cannot_buy": optional_str(token, "cannot_buy"),
            "cannot_sell_all": optional_str(token, "cannot_sell_all"),
            "slippage_modifiable": optional_str(token, "slippage_modifiable"),
            "is_blacklisted": optional_str(token, "is_blacklisted"),
            "is_whitelisted": optional_str(token, "is_whitelisted"),
            "is_in_dex": optional_str(token, "is_in_dex"),
            "trading_cooldown": optional_str(token, "trading_cooldown"),
            "personal_slippage_modifiable": optional_str(token, "personal_slippage_modifiable"),
            "anti_whale_modifiable": optional_str(token, "anti_whale_modifiable"),
            "can_pause": optional_str(token, "transfer_pausable"),
            "owner_address": optional_str(token, "owner_address"),
            "creator_address": optional_str(token, "creator_address"),
            "holder_count": optional_str(token, "holder_count"),
            "total_supply": optional_str(token, "total_supply"),
            "lp_holder_count": optional_str(token, "lp_holder_count"),
            "is_anti_whale": optional_str(token, "is_anti_whale"),
            "holder_top": token.get("holders") if isinstance(token.get("holders"), list) else [],
            "lp_holders": token.get("lp_holders") if isinstance(token.get("lp_holders"), list) else [],
            "dex": token.get("dex") if isinstance(token.get("dex"), list) else [],
            "trust_list": optional_str(token, "trust_list"),
        }
        return envelope(self.name, status=SourceStatus.OK, payload=parsed, data_quality=DataQuality.OK, confidence=0.9)
