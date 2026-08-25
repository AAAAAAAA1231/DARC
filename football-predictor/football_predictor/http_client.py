from __future__ import annotations

from typing import Any
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

from .config import USER_AGENT

_CTX = ssl.create_default_context()


class HttpError(RuntimeError):
    pass


def fetch_bytes(
    url: str,
    timeout: float = 20.0,
    retries: int = 3,
    headers: dict[str, str] | None = None,
) -> bytes:
    req_headers = {
        "User-Agent": USER_AGENT,
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }
    if headers:
        req_headers.update(headers)
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
                data = resp.read()
                if not data:
                    raise HttpError(f"空响应: {url}")
                # football-data.co.uk 对缺失文件有时返回 HTML 而不是 CSV
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if data.lstrip()[:1] in (b"<",) and "csv" in url.lower():
                    raise HttpError(f"非 CSV 响应: {url}")
                if "json" in ctype and data.lstrip()[:1] not in (b"{", b"["):
                    raise HttpError(f"非 JSON 响应: {url}")
                return data
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, HttpError, OSError) as exc:
            last = exc
            time.sleep(0.4 * (attempt + 1))
    raise HttpError(f"请求失败 {url}: {last}") from last


def fetch_text(url: str, **kwargs: Any) -> str:
    data = fetch_bytes(url, **kwargs)
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    return data.decode("utf-8", errors="replace")


def fetch_json(url: str, **kwargs: Any) -> Any:
    return json.loads(fetch_text(url, **kwargs))


def quote(value: str) -> str:
    return urllib.parse.quote(value)
