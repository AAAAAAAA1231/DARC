from __future__ import annotations

import argparse
import threading
import time
import webbrowser

import uvicorn

from web3_radar.config import DEFAULT_HOST, DEFAULT_PORT, ensure_dirs, load_settings


def main() -> None:
    ensure_dirs()
    settings = load_settings()
    parser = argparse.ArgumentParser(description="链上雷达")
    parser.add_argument("--host", default=settings.get("host") or DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=int(settings.get("port") or DEFAULT_PORT))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    uvicorn.run("web3_radar.api:app", host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    time.sleep(0)
    main()
