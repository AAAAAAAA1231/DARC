from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TokenSnapshot:
    chain: str
    dex: str
    name: str
    symbol: str
    address: str
    pair_address: str
    price_usd: Optional[float]
    fdv_usd: Optional[float]
    mcap_usd: Optional[float]
    liquidity_usd: Optional[float]
    volume_h24: Optional[float]
    buys_h24: int = 0
    sells_h24: int = 0
    buyers_h24: int = 0
    sellers_h24: int = 0
    price_change_h24: Optional[float] = None
    pool_created_at: Optional[datetime] = None
    url: str = ""
    description: str = ""
    source: str = ""

    @property
    def size_usd(self) -> Optional[float]:
        for value in (self.mcap_usd, self.fdv_usd):
            if value and value > 0:
                return value
        return None

    @property
    def age_days(self) -> Optional[float]:
        if not self.pool_created_at:
            return None
        created = self.pool_created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        return max((utcnow() - created).total_seconds() / 86400.0, 0.0)

    @property
    def liq_to_size(self) -> Optional[float]:
        size = self.size_usd
        if not size or not self.liquidity_usd:
            return None
        return self.liquidity_usd / size

    @property
    def vol_to_size(self) -> Optional[float]:
        size = self.size_usd
        if not size or not self.volume_h24:
            return None
        return self.volume_h24 / size


@dataclass
class ScoreBreakdown:
    total: int
    venue: int
    narrative: int
    structure: int
    pillar: int
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    watch: bool = False
    priority: str = "skip"


@dataclass
class ScoredToken:
    token: TokenSnapshot
    score: ScoreBreakdown


@dataclass
class VenuePulse:
    chain: str
    dex: str
    token_count: int
    volume_h24: float
    median_age_days: Optional[float]
    label: str
    reasons: list[str] = field(default_factory=list)
    sample_symbols: list[str] = field(default_factory=list)
