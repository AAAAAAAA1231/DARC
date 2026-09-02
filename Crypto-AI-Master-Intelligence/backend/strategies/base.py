"""Strategy plugin contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np


@dataclass(slots=True)
class StrategySignal:
    name: str
    direction: str
    score: float
    confidence: float
    signal: str
    reasons: list[str] = field(default_factory=list)
    against: list[str] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "direction": self.direction,
            "score": round(self.score, 2),
            "confidence": round(self.confidence, 4),
            "signal": self.signal,
            "reason": self.reasons,
            "against": self.against,
            "extra": self.extra,
        }


class StrategyPlugin:
    name: str
    initial_weight: float = 1.0 / 14.0
    min_weight: float = 0.02
    max_weight: float = 0.18

    def evaluate(self, ohlcv: dict[str, np.ndarray]) -> StrategySignal:
        raise NotImplementedError
