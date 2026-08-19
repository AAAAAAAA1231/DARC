from __future__ import annotations

import argparse
import multiprocessing
import socket
import sys
import threading
import time
import traceback
import webbrowser

import uvicorn

from dengju.api import app
from dengju.config import DEFAULT_HOST, DEFAULT_PORT, STATIC_DIR, ensure_dirs
from dengju.engine.select import select_lighting


def _wait_and_open(host: str, port: int, url: str) -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.4)
    print(f"请手动打开：{url}", flush=True)


def main() -> None:
    multiprocessing.freeze_support()
    ensure_dirs()
    parser = argparse.ArgumentParser(description="灯具选型工具")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--text", default="普通办公室 7.2x9.0 300lx")
    args = parser.parse_args()
    if args.cli:
        doc = select_lighting({"text": args.text})
        print(doc["selected"])
        print(doc["warnings"] or "校核通过")
        return
    url = f"http://{args.host}:{args.port}"
    print("=" * 50, flush=True)
    print("灯具选型工具正在启动，请不要关闭这个窗口。", flush=True)
    print(f"启动后请打开：{url}", flush=True)
    print("本机离线运行。可输入房间参数或上传 CAD/PDF。", flush=True)
    print("=" * 50, flush=True)
    if not args.no_browser:
        threading.Thread(target=_wait_and_open, args=(args.host, args.port, url), daemon=True).start()
    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info", factory=False)
    except Exception:
        traceback.print_exc()
        if getattr(sys, "frozen", False):
            input("按回车键退出...")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
