from __future__ import annotations

from dataclasses import asdict, dataclass, field, is_dataclass
from typing import Any


def _dump(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dump(v) for k, v in asdict(obj).items()}
    if isinstance(obj, list):
        return [_dump(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _dump(v) for k, v in obj.items()}
    return obj


@dataclass
class TxWindow:
    buys: int = 0
    sells: int = 0
    buyers: int = 0
    sellers: int = 0


@dataclass
class PumpState:
    complete: bool = False
    real_sol: float = 0.0
    reply_count: int = 0
    livestream: bool = False
    nsfw: bool = False
    bonding_curve: str | None = None
    creator: str | None = None
    ath_mc: float = 0.0


@dataclass
class SecurityState:
    rugged: bool = False
    score: int | None = None
    score_normalised: int | None = None
    mint_authority: str | None = None
    freeze_authority: str | None = None
    lp_locked_pct: float | None = None
    holders: int | None = None
    top_holder_pct: float | None = None
    insider_networks: int | None = None
    risks: list[str] = field(default_factory=list)


@dataclass
class TokenSnapshot:
    chain: str
    address: str
    symbol: str
    name: str
    dex: str
    source: str
    pair_address: str | None = None
    price_usd: float = 0.0
    market_cap_usd: float = 0.0
    fdv_usd: float = 0.0
    liquidity_usd: float | None = None
    created_at_ms: int = 0
    volume_m5: float = 0.0
    volume_h1: float = 0.0
    volume_h6: float = 0.0
    volume_h24: float = 0.0
    change_m5: float = 0.0
    change_h1: float = 0.0
    change_h6: float = 0.0
    change_h24: float = 0.0
    tx_m5: TxWindow = field(default_factory=TxWindow)
    tx_m15: TxWindow = field(default_factory=TxWindow)
    tx_h1: TxWindow = field(default_factory=TxWindow)
    image: str | None = None
    websites: list[str] = field(default_factory=list)
    socials: list[dict[str, str]] = field(default_factory=list)
    boost_amount: int = 0
    has_profile: bool = False
    pump: PumpState | None = None
    security: SecurityState | None = None
    url: str | None = None

    @property
    def key(self) -> str:
        return f"{self.chain}:{self.address.lower()}"

    def cap(self) -> float:
        return self.market_cap_usd or self.fdv_usd or 0.0


@dataclass
class Gene:
    id: str
    name: str
    score: float
    max: float
    reason: str


@dataclass
class ScoreCard:
    total: int
    grade: str
    passed: bool
    kill_reasons: list[str]
    genes: list[Gene]
    x100_target_mc: float
    x_if_1m5: float
    x_if_5m: float
    x_if_20m: float
    feasibility: float
    band: str
    verdict: str
    thesis: str


@dataclass
class RankedToken:
    token: TokenSnapshot
    score: ScoreCard
    age_min: float

    def to_api(self) -> dict[str, Any]:
        payload = {
            "token": _dump(self.token),
            "score": _dump(self.score),
            "age_min": round(self.age_min, 2),
        }
        return payload
