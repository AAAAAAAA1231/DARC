from __future__ import annotations

import ssl
from typing import Any

import httpx

try:
    import certifi
    _VERIFY: ssl.SSLContext | bool = ssl.create_default_context(cafile=certifi.where())
except Exception:
    _VERIFY = True

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 ChainRadar/1.0",
    "Accept": "application/json,text/plain,*/*",
}


def client(timeout: float = 25.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        headers=DEFAULT_HEADERS,
        verify=_VERIFY,
    )


async def get_json(url: str, params: dict[str, Any] | None = None, timeout: float = 25.0) -> Any:
    async with client(timeout) as c:
        resp = await c.get(url, params=params)
        resp.raise_for_status()
        return resp.json()
