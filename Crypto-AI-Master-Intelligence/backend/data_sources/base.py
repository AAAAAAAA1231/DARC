"""Provider contracts. Business code never talks to vendor JSON directly."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import utcnow


@dataclass(slots=True)
class QualityEnvelope:
    source: str
    status: SourceStatus
    retrieved_at: datetime
    timestamp: datetime | None = None
    confidence: float = 0.0
    data_quality: DataQuality = DataQuality.MISSING
    payload: Any = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "status": self.status.value,
            "retrieved_at": self.retrieved_at.isoformat(),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "confidence": self.confidence,
            "data_quality": self.data_quality.value,
            "error": self.error,
            "meta": self.meta,
            "payload": self.payload,
        }

    @property
    def ok(self) -> bool:
        return self.status == SourceStatus.OK and self.payload is not None


def envelope(
    source: str,
    *,
    status: SourceStatus,
    payload: Any = None,
    timestamp: datetime | None = None,
    confidence: float = 0.0,
    data_quality: DataQuality = DataQuality.MISSING,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
) -> QualityEnvelope:
    return QualityEnvelope(
        source=source,
        status=status,
        retrieved_at=utcnow(),
        timestamp=timestamp,
        confidence=confidence,
        data_quality=data_quality,
        payload=payload,
        error=error,
        meta=meta or {},
    )


class DataProvider(ABC):
    name: str

    @abstractmethod
    async def health(self) -> QualityEnvelope:
        raise NotImplementedError

    def required_keys(self) -> list[str]:
        return []
