from __future__ import annotations

import threading
import time
import webbrowser

import uvicorn

from a_share_trading import config
from a_share_trading.webapp import app


def _open_browser(url: str) -> None:
    time.sleep(0.9)
    try:
        webbrowser.open(url)
    except Exception:
        pass


def _run_server(host: str, port: int) -> None:
    uvicorn.run(app, host=host, port=port, log_level="warning", access_log=False)


def main() -> None:
    host = "127.0.0.1"
    port = config.DEFAULT_PORT
    url = f"http://{host}:{port}/"
    threading.Thread(target=_run_server, args=(host, port), daemon=True).start()
    threading.Thread(target=_open_browser, args=(url,), daemon=True).start()

    try:
        import tkinter as tk
    except Exception:
        print(f"大A量化研判系统已启动：{url}")
        print("关闭本窗口即退出。")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            return
        return

    root = tk.Tk()
    root.title("大A量化研判系统")
    root.geometry("420x220")
    root.resizable(False, False)
    tk.Label(root, text="大A量化研判系统", font=("Microsoft YaHei", 16, "bold")).pack(pady=(18, 6))
    tk.Label(root, text="研究工具，不构成投资建议", fg="#666").pack()
    tk.Label(root, text=url, fg="#1d4ed8").pack(pady=8)
    tk.Button(root, text="打开浏览器", command=lambda: webbrowser.open(url), width=18).pack(pady=6)
    tk.Label(root, text="关闭本窗口即停止程序", fg="#888").pack(pady=(12, 0))
    root.mainloop()


if __name__ == "__main__":
    main()
