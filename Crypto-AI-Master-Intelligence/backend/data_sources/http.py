"""Shared async HTTP client with timeout, rate-limit, and schema-safe handling."""

from __future__ import annotations

from typing import Any

import httpx

from backend.core.enums import DataQuality, SourceStatus
from backend.core.logging import get_logger
from backend.data_sources.base import QualityEnvelope, envelope

logger = get_logger("http")


class HttpClient:
    def __init__(self, source: str, timeout_sec: float = 20.0, headers: dict[str, str] | None = None) -> None:
        self.source = source
        self.timeout_sec = timeout_sec
        self.headers = headers or {}

    async def get_json(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expect: type = (dict, list),
    ) -> QualityEnvelope:
        merged = {**self.headers, **(headers or {})}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec, headers=merged, follow_redirects=True) as client:
                response = await client.get(url, params=params)
        except httpx.TimeoutException as exc:
            logger.warning("timeout source=%s url=%s", self.source, url)
            return envelope(self.source, status=SourceStatus.TIMEOUT, data_quality=DataQuality.ERROR, error=str(exc))
        except httpx.HTTPError as exc:
            logger.warning("network_error source=%s url=%s err=%s", self.source, url, exc)
            return envelope(
                self.source, status=SourceStatus.NETWORK_ERROR, data_quality=DataQuality.ERROR, error=str(exc)
            )

        if response.status_code == 429:
            return envelope(
                self.source,
                status=SourceStatus.RATE_LIMITED,
                data_quality=DataQuality.ERROR,
                error="HTTP 429",
                meta={"status_code": 429},
            )
        if response.status_code >= 400:
            status = SourceStatus.UNKNOWN_ERROR
            if response.status_code in (401,):
                status = SourceStatus.MISSING_KEY
            return envelope(
                self.source,
                status=status,
                data_quality=DataQuality.ERROR,
                error=f"HTTP {response.status_code}",
                meta={"status_code": response.status_code, "body": response.text[:500], "url": url},
            )
        try:
            payload = response.json()
        except ValueError as exc:
            return envelope(
                self.source, status=SourceStatus.SCHEMA_ERROR, data_quality=DataQuality.INVALID, error=str(exc)
            )
        if not isinstance(payload, expect):
            return envelope(
                self.source,
                status=SourceStatus.SCHEMA_ERROR,
                data_quality=DataQuality.INVALID,
                error=f"expected {expect}, got {type(payload).__name__}",
            )
        return envelope(
            self.source,
            status=SourceStatus.OK,
            payload=payload,
            data_quality=DataQuality.OK,
            confidence=1.0,
            meta={"status_code": response.status_code, "url": url},
        )

    async def get_text(
        self,
        url: str,
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> QualityEnvelope:
        merged = {**self.headers, **(headers or {})}
        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec, headers=merged, follow_redirects=True) as client:
                response = await client.get(url, params=params)
        except httpx.TimeoutException as exc:
            return envelope(self.source, status=SourceStatus.TIMEOUT, data_quality=DataQuality.ERROR, error=str(exc))
        except httpx.HTTPError as exc:
            return envelope(self.source, status=SourceStatus.NETWORK_ERROR, data_quality=DataQuality.ERROR, error=str(exc))
        if response.status_code == 429:
            return envelope(self.source, status=SourceStatus.RATE_LIMITED, data_quality=DataQuality.ERROR, error="HTTP 429", meta={"status_code": 429})
        if response.status_code >= 400:
            return envelope(
                self.source,
                status=SourceStatus.UNKNOWN_ERROR,
                data_quality=DataQuality.ERROR,
                error=f"HTTP {response.status_code}",
                meta={"status_code": response.status_code, "body": response.text[:400], "url": url},
            )
        return envelope(
            self.source,
            status=SourceStatus.OK,
            payload=response.text,
            data_quality=DataQuality.OK,
            confidence=1.0,
            meta={"status_code": response.status_code, "url": url, "content_type": response.headers.get("content-type")},
        )

    async def get_json_failover(
        self,
        urls: list[str],
        *,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        expect: type = (dict, list),
    ) -> QualityEnvelope:
        last: QualityEnvelope | None = None
        for url in urls:
            env = await self.get_json(url, params=params, headers=headers, expect=expect)
            if env.ok:
                env.meta["resolved_url"] = url
                return env
            last = env
            code = (env.meta or {}).get("status_code")
            if env.status in {SourceStatus.TIMEOUT, SourceStatus.NETWORK_ERROR} or code in {403, 451, 502, 503, 520}:
                logger.warning("failover source=%s url=%s status=%s", self.source, url, env.status.value)
                continue
            return env
        return last or envelope(self.source, status=SourceStatus.NETWORK_ERROR, data_quality=DataQuality.ERROR, error="no urls")
