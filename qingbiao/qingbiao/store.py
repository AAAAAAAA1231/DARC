from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from qingbiao.config import DATA_DIR, UPLOAD_DIR, ensure_dirs

SESSION_PATH = DATA_DIR / "session.json"


def _empty() -> dict[str, Any]:
    return {
        "project": {
            "name": "",
            "floors": "",
            "area": "",
            "structure": "",
            "foundation": "",
            "seismic": "",
            "notes": "",
        },
        "economic": {"limit": None, "bidders": []},
        "technical": {"bidders": []},
        "cad": {"file": None},
        "results": {},
        "settings": {"similar_price_pct": 0.5, "text_similar_pct": 86.0},
    }


class Store:
    def __init__(self) -> None:
        ensure_dirs()
        self.data = _empty()
        if SESSION_PATH.exists():
            try:
                self.data = json.loads(SESSION_PATH.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.data = _empty()

    def save(self) -> None:
        ensure_dirs()
        SESSION_PATH.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")

    def reset(self) -> None:
        self.data = _empty()
        self.save()

    def save_upload(self, kind: str, filename: str, content: bytes) -> Path:
        folder = UPLOAD_DIR / kind
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / f"{uuid.uuid4().hex[:8]}_{filename}"
        dest.write_bytes(content)
        return dest


store = Store()
