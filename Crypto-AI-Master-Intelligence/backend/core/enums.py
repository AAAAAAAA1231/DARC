"""Shared enumerations. These are domain vocabularies, not market universes."""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    PENDING = "PENDING"
    FOLLOWING = "FOLLOWING"
    HIGH_PRIORITY = "HIGH_PRIORITY"
    WATCHING = "WATCHING"
    PARTICIPATED = "PARTICIPATED"
    COMPLETED = "COMPLETED"
    ABANDONED = "ABANDONED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"


HIDDEN_PROJECT_STATUSES = frozenset(
    {
        ProjectStatus.ABANDONED,
        ProjectStatus.REJECTED,
        ProjectStatus.COMPLETED,
        ProjectStatus.EXPIRED,
    }
)


class PositionStatus(StrEnum):
    NO_POSITION = "NO_POSITION"
    OPEN = "OPEN"
    PARTIAL_EXIT = "PARTIAL_EXIT"
    CLOSED = "CLOSED"


class SecurityVerdict(StrEnum):
    SAFE = "SAFE"
    LOW_RISK = "LOW_RISK"
    MEDIUM_RISK = "MEDIUM_RISK"
    HIGH_RISK = "HIGH_RISK"
    MALICIOUS = "MALICIOUS"
    UNKNOWN = "UNKNOWN"
    NATIVE_PROTOCOL = "NATIVE_PROTOCOL"


RECOMMENDATION_BLOCKED_VERDICTS = frozenset(
    {
        SecurityVerdict.MALICIOUS,
        SecurityVerdict.HIGH_RISK,
        SecurityVerdict.UNKNOWN,
    }
)


class DataQuality(StrEnum):
    OK = "ok"
    STALE = "stale"
    PARTIAL = "partial"
    INVALID = "invalid"
    MISSING = "missing"
    ERROR = "error"


class SourceStatus(StrEnum):
    OK = "ok"
    MISSING_KEY = "missing_key"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NETWORK_ERROR = "network_error"
    SCHEMA_ERROR = "schema_error"
    DISABLED = "disabled"
    UNKNOWN_ERROR = "unknown_error"


class ModuleName(StrEnum):
    RADAR_50X = "50X"
    FUTURES = "FUTURES"
    SPOT = "SPOT"
    AIRDROP = "AIRDROP"
    LAUNCH = "LAUNCH"
    FOOTBALL = "FOOTBALL"
    LOTTERY = "LOTTERY"


class ModelSignal(StrEnum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    ADD = "ADD"
    TAKE_PROFIT = "TAKE_PROFIT"
    REDUCE = "REDUCE"
    EXIT = "EXIT"
    HIGH_RISK = "HIGH_RISK"
    LONG = "LONG"
    SHORT = "SHORT"
    FOLLOW = "FOLLOW"
    REJECT = "REJECT"
    NEUTRAL = "NEUTRAL"


class MarketRegime(StrEnum):
    BULL = "BULL"
    BEAR = "BEAR"
    TRANSITION = "TRANSITION"
    RANGE = "RANGE"


class LaunchClass(StrEnum):
    A = "A"
    B = "B"
    C = "C"


class RiskProfile(StrEnum):
    CONSERVATIVE = "CONSERVATIVE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"


class SimulationStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NarrativeTag(StrEnum):
    AI = "AI"
    DEPIN = "DEPIN"
    RWA = "RWA"
    DEFI = "DEFI"
    BTCFI = "BTCFI"
    LAYER2 = "LAYER2"
    LAYER1 = "LAYER1"
    MEME = "MEME"
    GAMING = "GAMING"
    INFRA = "INFRA"
    RESTAKING = "RESTAKING"
    STABLECOIN = "STABLECOIN"
    PRIVACY = "PRIVACY"
    SOCIALFI = "SOCIALFI"
    DESCI = "DESCI"
    EMERGING = "EMERGING"
    UNKNOWN = "UNKNOWN"
