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

from shexiangtou.api import app
from shexiangtou.config import DEFAULT_HOST, DEFAULT_PORT, ensure_dirs
from shexiangtou.engine.place import layout_cameras


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
    parser = argparse.ArgumentParser(description="摄像头布置生成器")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--cli", action="store_true")
    parser.add_argument("--text", default="办公室 12x8 层高3.0 2个门")
    args = parser.parse_args()
    if args.cli:
        doc = layout_cameras({"description": args.text})
        print(doc.get("qty") or doc.get("error"))
        print(doc.get("warnings") or "校核通过")
        return
    url = f"http://{args.host}:{args.port}"
    print("=" * 50, flush=True)
    print("摄像头布置生成器正在启动，请不要关闭这个窗口。", flush=True)
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
