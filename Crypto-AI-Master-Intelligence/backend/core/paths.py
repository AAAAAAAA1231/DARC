"""Runtime paths. Frozen EXE keeps UI/config in the bundle and writes SQLite/.env next to the exe."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _roots() -> tuple[Path, Path]:
    if getattr(sys, "frozen", False):
        data_root = Path(sys.executable).resolve().parent
        bundle_root = Path(getattr(sys, "_MEIPASS", data_root))
        return bundle_root, data_root
    here = Path(__file__).resolve().parents[2]
    return here, here


BUNDLE_ROOT, DATA_ROOT = _roots()
PROJECT_ROOT = DATA_ROOT


def config_path() -> Path:
    bundled = BUNDLE_ROOT / "config" / "config.yaml"
    if bundled.exists():
        return bundled
    return DATA_ROOT / "config" / "config.yaml"


def frontend_dist() -> Path:
    return BUNDLE_ROOT / "frontend" / "dist"


def prepare_runtime() -> None:
    """Create writable folders beside the EXE and seed .env from the bundled example."""
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    (DATA_ROOT / "data").mkdir(exist_ok=True)
    (DATA_ROOT / "logs").mkdir(exist_ok=True)
    env = DATA_ROOT / ".env"
    example = BUNDLE_ROOT / ".env.example"
    if not env.exists() and example.exists():
        shutil.copy(example, env)
    os.chdir(DATA_ROOT)
