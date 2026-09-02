"""Binance spot + USDT-M futures. Public market data does not require keys."""

from __future__ import annotations

from typing import Any

from backend.core.config import get_settings
from backend.core.enums import DataQuality, SourceStatus
from backend.core.parsing import optional_float, optional_str, parse_decimal, parse_timestamp, require_mapping
from backend.data_sources.base import DataProvider, QualityEnvelope, envelope
from backend.data_sources.http import HttpClient


SPOT_BASES = (
    "https://api.binance.com",
    "https://www.binance.com",
    "https://data-api.binance.vision",
    "https://api.binance.us",
)
FUTURES_BASES = (
    "https://fapi.binance.com",
    "https://www.binance.com",
)


class BinanceProvider(DataProvider):
    name = "binance"

    def __init__(self) -> None:
        cfg = get_settings().yaml_config.get("providers", {}).get("binance", {})
        timeout = float(cfg.get("timeout_sec", 20))
        extra_spot = [str(cfg.get("spot_base")).rstrip("/")] if cfg.get("spot_base") else []
        extra_fut = [str(cfg.get("futures_base")).rstrip("/")] if cfg.get("futures_base") else []
        self.spot_bases = list(dict.fromkeys(extra_spot + list(SPOT_BASES)))
        self.futures_bases = list(dict.fromkeys(extra_fut + list(FUTURES_BASES)))
        self._spot_base: str | None = None
        self._futures_base: str | None = None
        self.http = HttpClient(self.name, timeout, {"User-Agent": "Crypto-AI-Master-Intelligence/1.0"})

    def _spot_urls(self, path: str) -> list[str]:
        bases = [self._spot_base] + self.spot_bases if self._spot_base else self.spot_bases
        return [f"{b.rstrip('/')}{path}" for b in bases if b]

    def _futures_urls(self, path: str) -> list[str]:
        bases = [self._futures_base] + self.futures_bases if self._futures_base else self.futures_bases
        return [f"{b.rstrip('/')}{path}" for b in bases if b]

    def _remember(self, env: QualityEnvelope, kind: str) -> QualityEnvelope:
        url = (env.meta or {}).get("resolved_url") or (env.meta or {}).get("url")
        if env.ok and url:
            if kind == "spot":
                self._spot_base = url.split("/api/")[0] if "/api/" in url else url.rsplit("/", 1)[0]
            else:
                # futures paths are /fapi/ or /futures/
                if "/fapi/" in url:
                    self._futures_base = url.split("/fapi/")[0]
                elif "/futures/" in url:
                    self._futures_base = url.split("/futures/")[0]
        return env

    async def health(self) -> QualityEnvelope:
        return self._remember(await self.http.get_json_failover(self._spot_urls("/api/v3/ping")), "spot")

    async def spot_ticker_24h(self) -> QualityEnvelope:
        raw = self._remember(
            await self.http.get_json_failover(self._spot_urls("/api/v3/ticker/24hr"), expect=list),
            "spot",
        )
        if not raw.ok:
            return raw
        parsed: list[dict[str, Any]] = []
        for item in raw.payload:
            if not isinstance(item, dict):
                continue
            symbol = optional_str(item, "symbol")
            last = parse_decimal(item.get("lastPrice"))
            if not symbol or last is None:
                continue
            parsed.append(
                {
                    "symbol": symbol,
                    "last": str(last),
                    "price_change_pct": optional_float(item, "priceChangePercent"),
                    "volume": str(parse_decimal(item.get("volume")) or 0),
                    "quote_volume": str(parse_decimal(item.get("quoteVolume")) or 0),
                    "high": str(parse_decimal(item.get("highPrice")) or 0),
                    "low": str(parse_decimal(item.get("lowPrice")) or 0),
                    "open": str(parse_decimal(item.get("openPrice")) or 0),
                    "trades": item.get("count"),
                    "close_time": parse_timestamp(item.get("closeTime")).isoformat()
                    if parse_timestamp(item.get("closeTime"))
                    else None,
                }
            )
        quality = DataQuality.OK if parsed else DataQuality.PARTIAL
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload=parsed,
            data_quality=quality,
            confidence=1.0 if parsed else 0.2,
            timestamp=parse_timestamp(raw.payload[0].get("closeTime")) if raw.payload else None,
        )

    async def futures_ticker_24h(self) -> QualityEnvelope:
        raw = self._remember(
            await self.http.get_json_failover(self._futures_urls("/fapi/v1/ticker/24hr"), expect=list),
            "futures",
        )
        if not raw.ok:
            return raw
        parsed: list[dict[str, Any]] = []
        for item in raw.payload:
            if not isinstance(item, dict):
                continue
            symbol = optional_str(item, "symbol")
            last = parse_decimal(item.get("lastPrice"))
            quote = parse_decimal(item.get("quoteVolume"))
            if not symbol or last is None or quote is None:
                continue
            if not symbol.endswith("USDT"):
                continue
            parsed.append(
                {
                    "symbol": symbol,
                    "last": str(last),
                    "price_change_pct": optional_float(item, "priceChangePercent"),
                    "volume": str(parse_decimal(item.get("volume")) or 0),
                    "quote_volume": str(quote),
                    "high": str(parse_decimal(item.get("highPrice")) or 0),
                    "low": str(parse_decimal(item.get("lowPrice")) or 0),
                    "open": str(parse_decimal(item.get("openPrice")) or 0),
                    "close_time": parse_timestamp(item.get("closeTime")).isoformat()
                    if parse_timestamp(item.get("closeTime"))
                    else None,
                }
            )
        parsed.sort(key=lambda row: float(row["quote_volume"]), reverse=True)
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload=parsed,
            data_quality=DataQuality.OK if parsed else DataQuality.PARTIAL,
            confidence=1.0 if parsed else 0.2,
        )

    async def klines(self, symbol: str, interval: str = "1d", limit: int = 500, *, futures: bool = False) -> QualityEnvelope:
        path = "/fapi/v1/klines" if futures else "/api/v3/klines"
        urls = self._futures_urls(path) if futures else self._spot_urls(path)
        raw = self._remember(
            await self.http.get_json_failover(
                urls,
                params={"symbol": symbol, "interval": interval, "limit": limit},
                expect=list,
            ),
            "futures" if futures else "spot",
        )
        if not raw.ok:
            return raw
        candles: list[dict[str, Any]] = []
        for row in raw.payload:
            if not isinstance(row, list) or len(row) < 6:
                continue
            open_time = parse_timestamp(row[0])
            o, h, l, c, v = (parse_decimal(row[i]) for i in range(1, 6))
            if None in (open_time, o, h, l, c, v):
                continue
            candles.append(
                {
                    "open_time": open_time.isoformat(),
                    "open": str(o),
                    "high": str(h),
                    "low": str(l),
                    "close": str(c),
                    "volume": str(v),
                }
            )
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload=candles,
            data_quality=DataQuality.OK if candles else DataQuality.PARTIAL,
            confidence=1.0 if candles else 0.2,
            timestamp=parse_timestamp(candles[-1]["open_time"]) if candles else None,
        )

    async def funding_rate(self, symbol: str, limit: int = 30) -> QualityEnvelope:
        raw = self._remember(
            await self.http.get_json_failover(
                self._futures_urls("/fapi/v1/fundingRate"),
                params={"symbol": symbol, "limit": limit},
                expect=list,
            ),
            "futures",
        )
        if not raw.ok:
            return raw
        rows = []
        for item in raw.payload:
            if not isinstance(item, dict):
                continue
            rate = parse_decimal(item.get("fundingRate"))
            ts = parse_timestamp(item.get("fundingTime"))
            if rate is None:
                continue
            rows.append({"funding_rate": str(rate), "time": ts.isoformat() if ts else None})
        return envelope(self.name, status=SourceStatus.OK, payload=rows, data_quality=DataQuality.OK, confidence=1.0)

    async def open_interest(self, symbol: str) -> QualityEnvelope:
        raw = self._remember(
            await self.http.get_json_failover(
                self._futures_urls("/fapi/v1/openInterest"),
                params={"symbol": symbol},
                expect=dict,
            ),
            "futures",
        )
        if not raw.ok:
            return raw
        try:
            body = require_mapping(raw.payload, "openInterest")
        except ValueError as exc:
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error=str(exc))
        oi = parse_decimal(body.get("openInterest"))
        ts = parse_timestamp(body.get("time"))
        if oi is None:
            return envelope(self.name, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error="missing openInterest")
        return envelope(
            self.name,
            status=SourceStatus.OK,
            payload={"open_interest": str(oi), "time": ts.isoformat() if ts else None},
            timestamp=ts,
            data_quality=DataQuality.OK,
            confidence=1.0,
        )

    async def long_short_ratio(self, symbol: str, period: str = "1h", limit: int = 30) -> QualityEnvelope:
        raw = self._remember(
            await self.http.get_json_failover(
                self._futures_urls("/futures/data/globalLongShortAccountRatio"),
                params={"symbol": symbol, "period": period, "limit": limit},
                expect=list,
            ),
            "futures",
        )
        if not raw.ok:
            return raw
        rows = []
        for item in raw.payload:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "long_short_ratio": optional_float(item, "longShortRatio"),
                    "long_account": optional_float(item, "longAccount"),
                    "short_account": optional_float(item, "shortAccount"),
                    "time": parse_timestamp(item.get("timestamp")).isoformat()
                    if parse_timestamp(item.get("timestamp"))
                    else None,
                }
            )
        return envelope(self.name, status=SourceStatus.OK, payload=rows, data_quality=DataQuality.OK, confidence=1.0)

    async def taker_buy_sell(self, symbol: str, period: str = "1h", limit: int = 30) -> QualityEnvelope:
        raw = self._remember(
            await self.http.get_json_failover(
                self._futures_urls("/futures/data/takerlongshortRatio"),
                params={"symbol": symbol, "period": period, "limit": limit},
                expect=list,
            ),
            "futures",
        )
        if not raw.ok:
            return raw
        rows = []
        for item in raw.payload:
            if not isinstance(item, dict):
                continue
            rows.append(
                {
                    "buy_sell_ratio": optional_float(item, "buySellRatio"),
                    "buy_vol": optional_float(item, "buyVol"),
                    "sell_vol": optional_float(item, "sellVol"),
                    "time": parse_timestamp(item.get("timestamp")).isoformat()
                    if parse_timestamp(item.get("timestamp"))
                    else None,
                }
            )
        return envelope(self.name, status=SourceStatus.OK, payload=rows, data_quality=DataQuality.OK, confidence=1.0)
