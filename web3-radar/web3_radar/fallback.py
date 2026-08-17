from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from web3_radar.config import APP_DIR

_CANDIDATES = [
    Path(__file__).resolve().parent / "resources" / "fallback.json",
    APP_DIR / "web3_radar" / "resources" / "fallback.json",
    APP_DIR / "resources" / "fallback.json",
]


def load_fallback() -> dict[str, Any]:
    for path in _CANDIDATES:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return {"ambassadors": [], "launches": [], "airdrops": []}


def merge_items(live: list[dict[str, Any]], seed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen = {str(x.get("key")) for x in live}
    out = list(live)
    for row in seed:
        if str(row.get("key")) not in seen:
            item = dict(row)
            item.setdefault("fallback", True)
            out.append(item)
    return out
