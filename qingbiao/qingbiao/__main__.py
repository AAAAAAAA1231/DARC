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

from qingbiao.api import app
from qingbiao.config import DEFAULT_HOST, DEFAULT_PORT, RESOURCES, STATIC_DIR, ensure_dirs


def _wait_and_open(host: str, port: int, url: str) -> None:
    deadline = time.time() + 60
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                webbrowser.open(url)
                return
        except OSError:
            time.sleep(0.4)
    print(f"服务启动较慢，请手动在浏览器打开：{url}", flush=True)


def main() -> None:
    multiprocessing.freeze_support()
    ensure_dirs()
    parser = argparse.ArgumentParser(description="清标助手")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print("=" * 50, flush=True)
    print("清标助手正在启动，请不要关闭这个黑窗口。", flush=True)
    print(f"启动后请打开：{url}", flush=True)
    print(f"界面目录：{STATIC_DIR} 存在={STATIC_DIR.exists()}", flush=True)
    print(f"规则库目录：{RESOURCES} 存在={RESOURCES.exists()}", flush=True)
    print("=" * 50, flush=True)

    if not args.no_browser:
        threading.Thread(target=_wait_and_open, args=(args.host, args.port, url), daemon=True).start()

    try:
        uvicorn.run(app, host=args.host, port=args.port, log_level="info", factory=False)
    except Exception:
        traceback.print_exc()
        print("\n启动失败。请把上面的英文报错截图发回来。", flush=True)
        if getattr(sys, "frozen", False):
            input("按回车键退出...")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
