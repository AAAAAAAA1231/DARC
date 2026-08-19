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

from shigongtu.api import app
from shigongtu.config import DEFAULT_HOST, DEFAULT_PORT, STATIC_DIR, ensure_dirs
from shigongtu.engine.generate import generate_package


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
    parser = argparse.ArgumentParser(description="建筑施工图自动生成器")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--cli", action="store_true", help="命令行生成一套示例图纸后退出")
    parser.add_argument("--name", default="××办公楼工程")
    parser.add_argument("--type", dest="building_type", default="办公楼")
    parser.add_argument("--floors", type=int, default=6)
    parser.add_argument("--floor-area", type=float, default=1200)
    args = parser.parse_args()
    if args.cli:
        doc = generate_package(
            {
                "name": args.name,
                "building_type": args.building_type,
                "floors": args.floors,
                "floor_area": args.floor_area,
            }
        )
        print(f"已生成 {doc['count']} 张图纸")
        print(doc["zip"])
        return
    url = f"http://{args.host}:{args.port}"
    print("=" * 50, flush=True)
    print("施工图生成器正在启动，请不要关闭这个窗口。", flush=True)
    print(f"启动后请打开：{url}", flush=True)
    print(f"界面目录：{STATIC_DIR} 存在={STATIC_DIR.exists()}", flush=True)
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
