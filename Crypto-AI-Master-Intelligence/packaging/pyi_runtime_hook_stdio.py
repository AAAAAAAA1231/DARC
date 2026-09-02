"""Earliest frozen startup: give windowed EXEs a real stdout/stderr.

console=False leaves sys.stdout/sys.stderr as None. uvicorn and logging then
crash on the first print, which looks like "double-click does nothing".
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path


def _attach() -> None:
    if not getattr(sys, "frozen", False):
        return
    root = Path(sys.executable).resolve().parent
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "desktop.log"
    handle = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    stamp = datetime.now(timezone.utc).isoformat()
    handle.write(f"{stamp} | runtime_hook pid={sys.executable}\n")
    if sys.stdout is None:
        sys.stdout = handle
    if sys.stderr is None:
        sys.stderr = handle


_attach()
