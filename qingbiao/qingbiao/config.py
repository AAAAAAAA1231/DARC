from __future__ import annotations

import sys
from pathlib import Path


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def _writable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = _bundle_dir()
ROOT_DIR = _writable_root()
DATA_DIR = ROOT_DIR / "data"
UPLOAD_DIR = DATA_DIR / "uploads"
_STATIC_CANDIDATES = [
    Path(__file__).resolve().parent / "static",
    APP_DIR / "qingbiao" / "static",
    APP_DIR / "static",
]
_RESOURCE_CANDIDATES = [
    Path(__file__).resolve().parent / "resources",
    APP_DIR / "qingbiao" / "resources",
    APP_DIR / "resources",
]
STATIC_DIR = next((p for p in _STATIC_CANDIDATES if p.exists()), _STATIC_CANDIDATES[0])
RESOURCES = next((p for p in _RESOURCE_CANDIDATES if p.exists()), _RESOURCE_CANDIDATES[0])

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8790
MIN_BIDDERS = 3
SIMILAR_PRICE_PCT = 0.005  # 0.5%
SIMILAR_ABS = 0.01
TEXT_SIMILAR_THRESHOLD = 0.86
AREA_TOLERANCE_PCT = 0.03


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
