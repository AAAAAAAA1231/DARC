"""Frozen-aware paths so the Windows EXE writes next to itself, not into a temp unpack dir."""

from __future__ import annotations

import sys
from pathlib import Path


APP_NAME = "AShareQuant"


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def bundle_dir() -> Path:
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def install_dir() -> Path:
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def user_home() -> Path:
    d = install_dir() / f"{APP_NAME}_data" if is_frozen() else install_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d


def output_dir() -> Path:
    d = user_home() / "output"
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_dir() -> Path:
    d = user_home() / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def log_path() -> Path:
    p = user_home() / "ashare_quant.log"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def default_config_candidates() -> list[Path]:
    return [
        user_home() / "config.yaml",
        install_dir() / "config" / "default.yaml",
        bundle_dir() / "config" / "default.yaml",
        Path(__file__).with_name("resources") / "default.yaml",
        Path(__file__).resolve().parents[2] / "config" / "default.yaml",
    ]


def resolve_config_path(path: str | Path | None = None) -> Path:
    if path:
        return Path(path)
    for cand in default_config_candidates():
        if cand.exists():
            return cand
    return default_config_candidates()[-1]
