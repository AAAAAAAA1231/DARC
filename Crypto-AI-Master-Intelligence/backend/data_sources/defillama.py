"""DefiLlama TVL and protocol directory. Public, no key."""

from __future__ import annotations

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_float, optional_str
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient


class DefiLlamaProvider(DataProvider):
    name = "defillama"

    def __init__(self) -> None:
        cfg = get_settings().yaml_config.get("providers", {}).get("defillama", {})
        self.base = str(cfg.get("base", "https://api.llama.fi")).rstrip("/")
        self.http = HttpClient(self.name, float(cfg.get("timeout_sec", 20)))

    async def health(self) -> QualityEnvelope:
        return await self.http.get_json(f"{self.base}/v2/chains", expect=list)

    async def protocols(self) -> QualityEnvelope:
        raw = await self.http.get_json(f"{self.base}/protocols", expect=list)
        if not raw.ok:
            return raw
        parsed = []
        for item in raw.payload:
            if not isinstance(item, dict):
                continue
            name = optional_str(item, "name")
            if not name:
                continue
            parsed.append(
                {
                    "name": name,
                    "slug": optional_str(item, "slug"),
                    "symbol": optional_str(item, "symbol"),
                    "tvl": optional_float(item, "tvl"),
                    "change_1d": optional_float(item, "change_1d"),
                    "change_7d": optional_float(item, "change_7d"),
                    "chain": optional_str(item, "chain"),
                    "category": optional_str(item, "category"),
                    "url": optional_str(item, "url"),
                    "twitter": optional_str(item, "twitter"),
                    "audits": optional_str(item, "audits"),
                    "gecko_id": optional_str(item, "gecko_id"),
                    "listed_at": item.get("listedAt"),
                }
            )
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload=parsed,
            data_quality=DataQuality.OK if parsed else DataQuality.PARTIAL,
            confidence=1.0 if parsed else 0.2,
        )
