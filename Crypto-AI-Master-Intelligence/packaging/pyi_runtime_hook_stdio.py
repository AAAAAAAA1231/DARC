"""Earliest frozen startup: stdio + loopback proxy bypass.

console=False leaves sys.stdout/sys.stderr as None. Clash/V2Ray system
proxy will intercept 127.0.0.1 and make the boot page look dead.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def _attach() -> None:
    os.environ["NO_PROXY"] = "127.0.0.1,localhost,::1"
    os.environ["no_proxy"] = os.environ["NO_PROXY"]
    os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = (
        "--proxy-server=direct:// --proxy-bypass-list=<-loopback>;127.0.0.1;localhost"
    )
    if not getattr(sys, "frozen", False):
        return
    root = Path(sys.executable).resolve().parent
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "desktop.log"
    handle = open(log_path, "a", encoding="utf-8", buffering=1)  # noqa: SIM115
    stamp = datetime.now(timezone.utc).isoformat()
    proxy = os.environ.get("HTTP_PROXY") or os.environ.get("http_proxy") or ""
    handle.write(f"{stamp} | runtime_hook exe={sys.executable} HTTP_PROXY={proxy}\n")
    if sys.stdout is None:
        sys.stdout = handle
    if sys.stderr is None:
        sys.stderr = handle


_attach()
