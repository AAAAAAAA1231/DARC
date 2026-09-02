"""Unified project identity. Chain+contract preferred; pre-token uses website+X+name."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _norm(value: str | None) -> str:
    return (value or "").strip().lower()


def _slug(value: str | None) -> str:
    return _NON_ALNUM.sub("-", _norm(value)).strip("-")


def is_evm_address(value: str | None) -> bool:
    if not value:
        return False
    text = value.strip()
    return text.startswith("0x") and len(text) == 42 and all(c in "0123456789abcdefABCDEF" for c in text[2:])


def normalize_contract(address: str | None) -> str:
    if not address:
        return ""
    text = address.strip()
    if is_evm_address(text):
        return text.lower()
    return text


def stable_hash(*parts: str) -> str:
    joined = "|".join(_norm(p) for p in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:16].upper()


@dataclass(frozen=True, slots=True)
class ProjectIdentity:
    project_id: str
    chain: str | None
    contract: str | None
    website: str | None
    twitter: str | None
    name: str
    identity_kind: str

    @property
    def dedup_key(self) -> str:
        if self.chain and self.contract:
            return f"{_norm(self.chain)}:{normalize_contract(self.contract)}"
        return f"web:{_norm(self.website)}:{_norm(self.twitter)}:{_norm(self.name)}"


def build_project_identity(
    *,
    name: str,
    chain: str | None = None,
    contract: str | None = None,
    website: str | None = None,
    twitter: str | None = None,
) -> ProjectIdentity:
    chain_n = _slug(chain) if chain else None
    contract_n = normalize_contract(contract) if contract else None
    if chain_n and contract_n:
        project_id = f"PROJECT-{chain_n.upper()}-{contract_n.upper()}"
        return ProjectIdentity(
            project_id=project_id,
            chain=chain_n,
            contract=contract_n,
            website=website,
            twitter=twitter,
            name=name,
            identity_kind="chain_contract",
        )
    digest = stable_hash(website or "", twitter or "", name)
    project_id = f"PROJECT-WEB-{digest}"
    return ProjectIdentity(
        project_id=project_id,
        chain=None,
        contract=None,
        website=website,
        twitter=twitter,
        name=name,
        identity_kind="pre_token",
    )
