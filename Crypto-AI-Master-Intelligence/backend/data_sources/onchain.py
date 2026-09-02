"""Free on-chain-adjacent BTC metrics. Not a substitute for MVRV/NUPL."""

from __future__ import annotations

from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_float
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient


class MempoolProvider(DataProvider):
    name = "mempool"

    def __init__(self) -> None:
        self.http = HttpClient(self.name, 20.0, {"User-Agent": "Crypto-AI-Master-Intelligence/1.0"})
        self.base = "https://mempool.space/api"

    async def health(self) -> QualityEnvelope:
        raw = await self.http.get_text(f"{self.base}/blocks/tip/height")
        if not raw.ok:
            return raw
        try:
            height = int(str(raw.payload).strip())
        except (TypeError, ValueError):
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error="height not int")
        return envelope(self.name, status=SourceStatus.OK, payload={"height": height}, data_quality=DataQuality.OK, confidence=1.0)

    async def hashrate(self) -> QualityEnvelope:
        raw = await self.http.get_json(f"{self.base}/v1/mining/hashrate/1m", expect=dict)
        if not raw.ok:
            return raw
        current = optional_float(raw.payload, "currentHashrate") if isinstance(raw.payload, dict) else None
        series = raw.payload.get("hashrates") if isinstance(raw.payload, dict) else None
        last = None
        if isinstance(series, list) and series and isinstance(series[-1], dict):
            last = optional_float(series[-1], "avgHashrate")
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload={"current_hashrate": current, "last_avg_hashrate": last},
            data_quality=DataQuality.OK,
            confidence=0.9,
        )


class BlockchainInfoProvider(DataProvider):
    name = "blockchain_info"

    def __init__(self) -> None:
        self.http = HttpClient(self.name, 20.0, {"User-Agent": "Crypto-AI-Master-Intelligence/1.0"})
        self.base = "https://api.blockchain.info"

    async def health(self) -> QualityEnvelope:
        return await self.chart("n-transactions", "7days")

    async def chart(self, name: str, timespan: str = "30days") -> QualityEnvelope:
        raw = await self.http.get_json(
            f"{self.base}/charts/{name}",
            params={"timespan": timespan, "format": "json"},
            expect=dict,
        )
        if not raw.ok:
            return raw
        values = raw.payload.get("values")
        if not isinstance(values, list) or not values:
            return envelope(self.name, status=SourceStatus.OK, payload=[], data_quality=DataQuality.MISSING, confidence=0.0)
        last = values[-1] if isinstance(values[-1], dict) else {}
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload={"name": raw.payload.get("name"), "unit": raw.payload.get("unit"), "last": last, "n": len(values)},
            data_quality=DataQuality.OK,
            confidence=1.0,
        )


class CoinPaprikaProvider(DataProvider):
    name = "coinpaprika"

    def __init__(self) -> None:
        self.http = HttpClient(self.name, 20.0)
        self.base = "https://api.coinpaprika.com/v1"

    async def health(self) -> QualityEnvelope:
        return await self.global_market()

    async def global_market(self) -> QualityEnvelope:
        raw = await self.http.get_json(f"{self.base}/global", expect=dict)
        if not raw.ok:
            return raw
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload={
                "market_cap_usd": optional_float(raw.payload, "market_cap_usd"),
                "volume_24h_usd": optional_float(raw.payload, "volume_24h_usd"),
                "btc_dominance": optional_float(raw.payload, "bitcoin_dominance_percentage"),
                "cryptocurrencies_number": raw.payload.get("cryptocurrencies_number"),
            },
            data_quality=DataQuality.OK,
            confidence=1.0,
        )
