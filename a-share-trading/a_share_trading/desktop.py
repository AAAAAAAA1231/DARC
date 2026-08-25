from __future__ import annotations

import asyncio
import socket
import sys
import threading
import time
import traceback
import webbrowser

import uvicorn

from a_share_trading import config


def _ensure_stdio() -> None:
    """Windowed PyInstaller sets stdout/stderr to None; uvicorn then crashes."""
    if sys.stdout is not None and sys.stderr is not None:
        return
    log_path = config.writable_root() / "a_share.log"
    handle = open(log_path, "a", encoding="utf-8", errors="replace")
    if sys.stdout is None:
        sys.stdout = handle
    if sys.stderr is None:
        sys.stderr = handle


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _pick_port(host: str, preferred: int) -> int:
    if not _port_open(host, preferred):
        return preferred
    sock = socket.socket()
    sock.bind((host, 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _run_server(host: str, port: int, error_box: list[str]) -> None:
    try:
        from a_share_trading.webapp import app

        uv_config = uvicorn.Config(
            app,
            host=host,
            port=port,
            log_level="warning",
            access_log=False,
            lifespan="off",
            loop="asyncio",
            http="h11",
        )
        server = uvicorn.Server(uv_config)
        asyncio.run(server.serve())
    except Exception:
        error_box.append(traceback.format_exc())


def _wait_ready(host: str, port: int, timeout: float = 12.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port):
            return True
        time.sleep(0.15)
    return False


def main() -> None:
    _ensure_stdio()
    host = "127.0.0.1"
    port = _pick_port(host, config.DEFAULT_PORT)
    url = f"http://{host}:{port}/"
    errors: list[str] = []
    threading.Thread(target=_run_server, args=(host, port, errors), daemon=True).start()
    ready = _wait_ready(host, port)
    if ready:
        try:
            webbrowser.open(url)
        except Exception:
            pass

    try:
        import tkinter as tk
        from tkinter import scrolledtext
    except Exception:
        print(f"大A量化研判系统已启动：{url}" if ready else "服务启动失败，见 a_share.log")
        if errors:
            print(errors[0])
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return
        return

    root = tk.Tk()
    root.title("大A量化研判系统")
    root.geometry("460x280")
    root.resizable(False, False)
    tk.Label(root, text="大A量化研判系统", font=("Microsoft YaHei", 16, "bold")).pack(pady=(16, 4))
    tk.Label(root, text="研究工具，不构成投资建议", fg="#666").pack()
    status = "服务已启动，浏览器将打开研判页" if ready else "服务启动失败（127.0.0.1 无法连接）"
    color = "#15803d" if ready else "#b91c1c"
    tk.Label(root, text=status, fg=color).pack(pady=(10, 0))
    tk.Label(root, text=url, fg="#1d4ed8").pack(pady=6)
    tk.Button(root, text="打开浏览器", command=lambda: webbrowser.open(url), width=18).pack(pady=4)
    if errors:
        box = scrolledtext.ScrolledText(root, height=6, width=54)
        box.pack(padx=12, pady=8)
        box.insert("1.0", errors[0])
        box.configure(state="disabled")
    else:
        tk.Label(root, text="关闭本窗口即停止程序", fg="#888").pack(pady=(10, 0))
    root.mainloop()


if __name__ == "__main__":
    main()
