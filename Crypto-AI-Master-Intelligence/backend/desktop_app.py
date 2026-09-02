"""Desktop entry: local API + pywebview window. No live trading."""

from __future__ import annotations

import multiprocessing
import threading
import time

from backend.core.paths import DATA_ROOT, prepare_runtime


def _serve() -> None:
    import uvicorn

    from backend.core.config import get_settings
    from backend.main import app

    settings = get_settings()
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")


def run() -> None:
    prepare_runtime()
    from backend.core.config import get_settings
    from backend.core.logging import get_logger

    log = get_logger("desktop")
    settings = get_settings()
    thread = threading.Thread(target=_serve, daemon=True)
    thread.start()
    url = f"http://{settings.host}:{settings.port}"
    for _ in range(80):
        time.sleep(0.25)
        try:
            import urllib.request

            urllib.request.urlopen(url + "/api/health", timeout=1)
            break
        except Exception:  # noqa: BLE001
            continue
    log.info("opening_window %s data_root=%s", url, DATA_ROOT)
    import webview

    webview.create_window(settings.app_name, url, width=1440, height=900)
    webview.start()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
