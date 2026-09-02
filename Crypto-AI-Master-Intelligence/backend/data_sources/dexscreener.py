"""DexScreener liquidity and pair data. Public, no key."""

from __future__ import annotations

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_float, optional_str, parse_timestamp
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient


class DexScreenerProvider(DataProvider):
    name = "dexscreener"

    def __init__(self) -> None:
        cfg = get_settings().yaml_config.get("providers", {}).get("dexscreener", {})
        self.base = str(cfg.get("base", "https://api.dexscreener.com")).rstrip("/")
        self.http = HttpClient(self.name, float(cfg.get("timeout_sec", 20)))

    async def health(self) -> QualityEnvelope:
        return await self.http.get_json(f"{self.base}/latest/dex/search", params={"q": "ETH"}, expect=dict)

    async def token_pairs(self, chain: str, token_address: str) -> QualityEnvelope:
        raw = await self.http.get_json(
            f"{self.base}/token-pairs/v1/{chain}/{token_address}",
            expect=(dict, list),
        )
        if not raw.ok:
            # fallback older path
            raw = await self.http.get_json(f"{self.base}/latest/dex/tokens/{token_address}", expect=dict)
            if not raw.ok:
                return raw
            pairs = raw.payload.get("pairs") if isinstance(raw.payload, dict) else None
        else:
            pairs = raw.payload if isinstance(raw.payload, list) else raw.payload.get("pairs")
        if not isinstance(pairs, list):
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error="pairs missing")
        parsed = []
        for item in pairs:
            if not isinstance(item, dict):
                continue
            liquidity = item.get("liquidity") if isinstance(item.get("liquidity"), dict) else {}
            volume = item.get("volume") if isinstance(item.get("volume"), dict) else {}
            parsed.append(
                {
                    "dex": optional_str(item, "dexId"),
                    "pair": optional_str(item, "pairAddress"),
                    "price_usd": optional_float(item, "priceUsd"),
                    "liquidity_usd": optional_float(liquidity, "usd"),
                    "volume_24h": optional_float(volume, "h24"),
                    "fdv": optional_float(item, "fdv"),
                    "market_cap": optional_float(item, "marketCap"),
                    "pair_created_at": parse_timestamp(item.get("pairCreatedAt")).isoformat()
                    if parse_timestamp(item.get("pairCreatedAt"))
                    else None,
                }
            )
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload=parsed,
            data_quality=DataQuality.OK if parsed else DataQuality.MISSING,
            confidence=0.8 if parsed else 0.0,
        )

    async def search(self, query: str) -> QualityEnvelope:
        raw = await self.http.get_json(f"{self.base}/latest/dex/search", params={"q": query}, expect=dict)
        if not raw.ok:
            return raw
        pairs = raw.payload.get("pairs") if isinstance(raw.payload, dict) else None
        if not isinstance(pairs, list):
            return envelope(self.name, status=SourceStatus.OK, payload=[], data_quality=DataQuality.MISSING, confidence=0.0)
        return envelope(self.name, status=SourceStatus.OK, payload=pairs[:50], data_quality=DataQuality.OK, confidence=0.7)
