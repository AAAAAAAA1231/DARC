from __future__ import annotations

import sys
from pathlib import Path


def repo_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parents[2]


def setup_sys_path() -> None:
    if getattr(sys, "frozen", False):
        return
    root = repo_root()
    for extra in (
        root / "fiftyx-radar",
        root / "football-predictor",
        root / "web3-radar",
        Path(__file__).resolve().parents[1],
    ):
        text = str(extra)
        if text not in sys.path:
            sys.path.insert(0, text)
