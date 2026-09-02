from __future__ import annotations

import argparse
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser

import uvicorn

from suite.boot import setup_sys_path

setup_sys_path()

from suite.server import app  # noqa: E402

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def open_in_browser(url: str) -> None:
    if sys.platform == "win32":
        try:
            os.startfile(url)  # type: ignore[attr-defined]
            return
        except OSError:
            pass
    try:
        webbrowser.open(url, new=2)
    except Exception:
        print(f"请手动打开：{url}", flush=True)


def _wait_and_open(host: str, port: int, url: str) -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                open_in_browser(url)
                return
        except OSError:
            time.sleep(0.3)
    print(f"启动较慢，请手动打开：{url}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="工作台：50倍雷达 / 三大联赛 / 合约分析 / 空投推荐")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args(argv)
    url = f"http://{args.host}:{args.port}/"
    print("工作台启动中，请不要关闭这个窗口。", flush=True)
    print(f"打开后请看浏览器：{url}", flush=True)
    if not args.no_browser:
        threading.Thread(target=_wait_and_open, args=(args.host, args.port, url), daemon=True).start()
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info", factory=False)
    except Exception:
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            input("启动失败，按回车退出…")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
