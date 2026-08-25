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

from web3_radar.api import app
from web3_radar.config import DEFAULT_HOST, DEFAULT_PORT, STATIC_DIR, ensure_dirs, load_settings


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
    settings = load_settings()
    parser = argparse.ArgumentParser(description="链上雷达")
    parser.add_argument("--host", default=settings.get("host") or DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=int(settings.get("port") or DEFAULT_PORT))
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print("=" * 50, flush=True)
    if sys.platform == "darwin":
        print("链上雷达正在启动，请不要退出。", flush=True)
    else:
        print("链上雷达正在启动，请不要关闭这个黑窗口。", flush=True)
    print(f"启动后请打开：{url}", flush=True)
    print(f"静态资源目录：{STATIC_DIR} 存在={STATIC_DIR.exists()}", flush=True)
    print("=" * 50, flush=True)

    if not args.no_browser:
        threading.Thread(target=_wait_and_open, args=(args.host, args.port, url), daemon=True).start()

    try:
        # Pass the app object, not an import string — required for PyInstaller EXE.
        uvicorn.run(app, host=args.host, port=args.port, log_level="info", factory=False)
    except Exception:
        traceback.print_exc()
        print("\n启动失败。请把上面的英文报错截图发回来。", flush=True)
        try:
            ensure_dirs()
            from web3_radar.config import DATA_DIR
            err_path = DATA_DIR / "last-error.txt"
            err_path.write_text(traceback.format_exc(), encoding="utf-8")
            print(f"错误已保存到 {err_path}", flush=True)
        except Exception:
            pass
        if getattr(sys, "frozen", False) and sys.stdin and sys.stdin.isatty():
            input("按回车键退出...")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
