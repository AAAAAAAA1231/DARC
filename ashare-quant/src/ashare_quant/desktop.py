"""Double-click desktop app: local server + today's idea sheet.

The Windows EXE entry point. Data is stored next to the executable
(AShareQuant_data/), not in the PyInstaller unpack directory.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

import pandas as pd

from .config import load_config
from .paper.simulator import DISCLAIMER
from .paths import data_dir, is_frozen, log_path, output_dir
from .pipeline import run_pipeline

PORT_RANGE = range(8765, 8780)
IDEA_COLS = [
    ("symbol", "代码"),
    ("name", "名称"),
    ("board_cn", "板块"),
    ("score", "分值"),
    ("action", "动作"),
    ("shares", "股数"),
    ("stop_loss", "止损"),
    ("take_profit", "止盈"),
    ("ci_p10", "P10"),
    ("ci_p50", "P50"),
    ("ci_p90", "P90"),
]


def _setup_logging() -> None:
    logging.basicConfig(
        filename=str(log_path()),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        encoding="utf-8",
    )
    logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))


def pick_port(host: str = "127.0.0.1") -> int:
    for port in PORT_RANGE:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError("8765-8779 端口均被占用")


def load_idea_rows(path: Path | None = None) -> list[dict]:
    csv_path = Path(path) if path else output_dir() / "ideas.csv"
    if not csv_path.exists():
        return []
    df = pd.read_csv(csv_path, dtype={"symbol": str})
    if "symbol" in df.columns:
        df["symbol"] = df["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
    return df.fillna("").to_dict(orient="records")


def run_job(mode: str, regenerate: bool, on_done=None) -> None:
    cfg = load_config()
    result = run_pipeline(
        cfg,
        output_dir=output_dir(),
        data_path=data_dir() / "synthetic_bars.csv",
        regenerate=regenerate,
        mode=mode,
    )
    if on_done:
        on_done(result)


def start_server_thread(port: int) -> threading.Thread:
    import uvicorn

    from .web.app import create_app

    cfg = load_config()
    app = create_app(cfg, output_dir=output_dir(), data_path=data_dir() / "synthetic_bars.csv")

    def _run() -> None:
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")

    t = threading.Thread(target=_run, name="ashare-web", daemon=True)
    t.start()
    return t


def open_browser(port: int) -> None:
    webbrowser.open(f"http://127.0.0.1:{port}/")


def main() -> int:
    _setup_logging()
    try:
        return _run_gui()
    except Exception:
        logging.exception("desktop failed")
        err = traceback.format_exc()
        log_path().write_text(log_path().read_text(encoding="utf-8") + "\n" + err, encoding="utf-8") if log_path().exists() else None
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("A股量化辅助", f"启动失败，日志见:\n{log_path()}\n\n{err[-800:]}")
        except Exception:
            print(err, file=sys.stderr)
        return 1


def _run_gui() -> int:
    import tkinter as tk
    from tkinter import ttk, messagebox

    port = pick_port()
    start_server_thread(port)

    root = tk.Tk()
    root.title("A股量化辅助系统")
    root.geometry("1180x720")
    root.minsize(960, 560)
    bg, card, text, muted, accent = "#0b1017", "#141c27", "#e7eef8", "#8b9bb0", "#3d8bfd"
    root.configure(bg=bg)

    style = ttk.Style()
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure("TFrame", background=bg)
    style.configure("TLabel", background=bg, foreground=text, font=("Microsoft YaHei UI", 10))
    style.configure("Title.TLabel", background=bg, foreground=text, font=("Microsoft YaHei UI", 16, "bold"))
    style.configure("Muted.TLabel", background=bg, foreground=muted, font=("Microsoft YaHei UI", 9))
    style.configure("Treeview", background=card, fieldbackground=card, foreground=text, rowheight=26, font=("Consolas", 9))
    style.configure("Treeview.Heading", background="#1b2636", foreground=text, font=("Microsoft YaHei UI", 9, "bold"))

    header = ttk.Frame(root)
    header.pack(fill="x", padx=16, pady=(14, 6))
    ttk.Label(header, text="A股量化辅助系统", style="Title.TLabel").pack(side="left")
    ttk.Label(header, text="双击即用 · 非实盘 · 非点预测", style="Muted.TLabel").pack(side="left", padx=12)

    warn = tk.Text(root, height=3, wrap="word", bg="#241a12", fg="#f0d5a6", relief="flat", font=("Microsoft YaHei UI", 9))
    warn.insert("1.0", DISCLAIMER + "  数据目录：" + str(output_dir().parent))
    warn.configure(state="disabled")
    warn.pack(fill="x", padx=16, pady=(0, 8))

    status = tk.StringVar(value=f"本地服务已启动  http://127.0.0.1:{port}/   正在准备今日信号…")
    ttk.Label(root, textvariable=status, style="Muted.TLabel").pack(fill="x", padx=16)

    btns = ttk.Frame(root)
    btns.pack(fill="x", padx=16, pady=8)

    columns = [c[0] for c in IDEA_COLS]
    tree = ttk.Treeview(root, columns=columns, show="headings")
    for key, title in IDEA_COLS:
        tree.heading(key, text=title)
        tree.column(key, width=88 if key != "name" else 110, anchor="center")
    vsb = ttk.Scrollbar(root, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    table_fr = ttk.Frame(root)
    table_fr.pack(fill="both", expand=True, padx=16, pady=(0, 12))
    tree.pack(in_=table_fr, side="left", fill="both", expand=True)
    vsb.pack(in_=table_fr, side="right", fill="y")

    busy = {"flag": False}

    def fill_table() -> None:
        for item in tree.get_children():
            tree.delete(item)
        rows = load_idea_rows()
        for row in rows:
            vals = []
            for key, _ in IDEA_COLS:
                v = row.get(key, "")
                if key in ("ci_p10", "ci_p50", "ci_p90") and v != "":
                    try:
                        v = f"{float(v) * 100:.1f}%"
                    except (TypeError, ValueError):
                        pass
                if key == "score" and v != "":
                    try:
                        v = f"{float(v):.3f}"
                    except (TypeError, ValueError):
                        pass
                vals.append(v)
            tree.insert("", "end", values=vals)
        buys = sum(1 for r in rows if str(r.get("action")) == "buy")
        status.set(f"本地服务  http://127.0.0.1:{port}/   候选 {len(rows)} 条，买入 {buys} 条。T+1：信号日收盘后产生，次日委托，最早再次一交易日可卖。")

    def spawn(mode: str, regenerate: bool, label: str) -> None:
        if busy["flag"]:
            messagebox.showinfo("请稍候", "已有任务在运行。")
            return
        busy["flag"] = True
        status.set(label)

        def worker() -> None:
            try:
                run_job(mode, regenerate)
                root.after(0, fill_table)
                root.after(0, lambda: status.set(f"完成。面板 http://127.0.0.1:{port}/"))
            except Exception as exc:
                logging.exception("job failed")
                root.after(0, lambda: messagebox.showerror("任务失败", str(exc)))
            finally:
                busy["flag"] = False

        threading.Thread(target=worker, daemon=True).start()

    tk.Button(btns, text="打开浏览器面板", bg=accent, fg="white", relief="flat", padx=12, pady=6, command=lambda: open_browser(port)).pack(side="left", padx=(0, 8))
    tk.Button(btns, text="刷新今日信号", bg="#223044", fg=text, relief="flat", padx=12, pady=6, command=lambda: spawn("quick", False, "正在计算今日信号（快速模式）…")).pack(side="left", padx=4)
    tk.Button(btns, text="完整验证 Walk-Forward", bg="#223044", fg=text, relief="flat", padx=12, pady=6, command=lambda: spawn("full", False, "正在 Walk-Forward + 蒙特卡洛（约数分钟）…")).pack(side="left", padx=4)
    tk.Button(btns, text="打开数据目录", bg="#223044", fg=text, relief="flat", padx=12, pady=6, command=lambda: os.startfile(str(output_dir())) if os.name == "nt" else webbrowser.open(output_dir().as_uri())).pack(side="left", padx=4)

    def bootstrap() -> None:
        if (output_dir() / "ideas.csv").exists():
            fill_table()
            root.after(600, lambda: open_browser(port))
            return
        spawn("quick", False, "首次启动：正在生成演示行情并计算信号，请稍候…")
        def _open_when_ready(n: int = 0) -> None:
            if (output_dir() / "ideas.csv").exists() or n > 120:
                open_browser(port)
                return
            root.after(1000, lambda: _open_when_ready(n + 1))
        root.after(4000, lambda: _open_when_ready(0))

    root.after(200, bootstrap)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
