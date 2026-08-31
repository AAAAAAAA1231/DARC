from __future__ import annotations

import asyncio
from typing import Any

import httpx

BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
SCANNER_UA = "GoldenDogRadar/1.0 (on-chain research scanner)"


def client_kwargs() -> dict[str, Any]:
    return {
        "timeout": httpx.Timeout(18.0, connect=6.0),
        "headers": {"User-Agent": SCANNER_UA, "Accept": "application/json"},
        "follow_redirects": True,
    }


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    browser: bool = False,
) -> Any:
    hdrs = dict(headers or {})
    if browser:
        hdrs.setdefault("User-Agent", BROWSER_UA)
        hdrs.setdefault("Accept", "application/json,text/plain,*/*")
        hdrs.setdefault("Origin", "https://pump.fun")
        hdrs.setdefault("Referer", "https://pump.fun/")
    try:
        resp = await client.get(url, params=params, headers=hdrs)
        if resp.status_code >= 400:
            return None
        ctype = resp.headers.get("content-type", "")
        if "json" not in ctype and not resp.text[:1] in "[{":
            return None
        return resp.json()
    except Exception:
        return None


async def gather_limited(coros: list, limit: int = 6) -> list[Any]:
    sem = asyncio.Semaphore(limit)

    async def wrap(coro):
        async with sem:
            try:
                return await coro
            except Exception:
                return None

    return await asyncio.gather(*[wrap(c) for c in coros])
