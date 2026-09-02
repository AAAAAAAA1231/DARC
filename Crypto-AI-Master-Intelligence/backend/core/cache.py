"""In-process TTL cache. Never used to invent data — only to avoid refetching a live envelope."""

from __future__ import annotations

import time
from typing import Any, TypeVar

T = TypeVar("T")

_STORE: dict[str, tuple[float, Any]] = {}


def get_cached(key: str) -> Any | None:
    row = _STORE.get(key)
    if not row:
        return None
    exp, value = row
    if exp < time.time():
        _STORE.pop(key, None)
        return None
    return value


def set_cached(key: str, value: Any, ttl_sec: float) -> Any:
    _STORE[key] = (time.time() + ttl_sec, value)
    return value
