from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import time
import hashlib

from .config import cache_dir


def _path(key: str) -> Path:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()
    return cache_dir() / f"{digest}.json"


def get_json(key: str, ttl_seconds: float) -> Any | None:
    path = _path(key)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    ts = float(payload.get("ts") or 0)
    if time.time() - ts > ttl_seconds:
        return None
    return payload.get("data")


def set_json(key: str, data: Any) -> None:
    path = _path(key)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"ts": time.time(), "data": data}, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(path)
