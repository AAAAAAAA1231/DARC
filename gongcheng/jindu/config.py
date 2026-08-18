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
DATA_DIR = ROOT_DIR / "data" / "jindu"
_STATIC = [
    Path(__file__).resolve().parent / "static",
    APP_DIR / "jindu" / "static",
    APP_DIR / "static",
]
_RES = [
    Path(__file__).resolve().parent / "resources",
    APP_DIR / "jindu" / "resources",
    APP_DIR / "resources",
]
STATIC_DIR = next((p for p in _STATIC if p.exists()), _STATIC[0])
RESOURCES = next((p for p in _RES if p.exists()), _RES[0])

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8793
WORKSPACE_FILE = "workspace.json"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
