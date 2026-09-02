"""Desktop entry: local API + pywebview window. No live trading."""

from __future__ import annotations

import threading
import time
import webview
import uvicorn

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.main import app

log = get_logger("desktop")


def _serve() -> None:
    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


def run() -> None:
    settings = get_settings()
    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    url = f"http://{settings.host}:{settings.port}"
    for _ in range(50):
        time.sleep(0.2)
        try:
            import urllib.request

            urllib.request.urlopen(url + "/api/health", timeout=1)
            break
        except Exception:  # noqa: BLE001
            continue
    log.info("opening_window %s", url)
    webview.create_window(settings.app_name, url, width=1440, height=900)
    webview.start()


if __name__ == "__main__":
    run()
