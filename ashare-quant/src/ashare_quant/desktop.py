"""Double-click desktop app: local window is the product; browser is optional."""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import traceback
import webbrowser
from pathlib import Path

import pandas as pd

from .config import load_config
from .paper.simulator import DISCLAIMER
from .panel_html import write_panel_html
from .paths import data_dir, log_path, output_dir
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


def port_is_open(host: str, port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def wait_for_listen(host: str, port: int, seconds: float = 12.0) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if port_is_open(host, port):
            return True
        time.sleep(0.2)
    return False


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
    write_panel_html(output_dir(), ideas=result.ideas.to_dict(orient="records") if not result.ideas.empty else [], snap=result.extra.get("snapshot"))
    if on_done:
        on_done(result)


def open_local_panel() -> Path:
    path = write_panel_html(output_dir())
    target = str(path.resolve())
    if os.name == "nt":
        os.startfile(target)
    else:
        webbrowser.open(path.resolve().as_uri())
    return path


def main() -> int:
    _setup_logging()
    try:
        return _run_gui()
    except Exception:
        logging.exception("desktop failed")
        err = traceback.format_exc()
        try:
            with log_path().open("a", encoding="utf-8") as fh:
                fh.write(err + "\n")
        except OSError:
            pass
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
    ttk.Label(header, text="单机运行 · 结果在本窗口，也可打开本地网页", style="Muted.TLabel").pack(side="left", padx=12)

    warn = tk.Text(root, height=3, wrap="word", bg="#241a12", fg="#f0d5a6", relief="flat", font=("Microsoft YaHei UI", 9))
    warn.insert(
        "1.0",
        DISCLAIMER + "  数据目录：" + str(output_dir().parent) + f"  日志：{log_path()}",
    )
    warn.configure(state="disabled")
    warn.pack(fill="x", padx=16, pady=(0, 8))

    status = tk.StringVar(value="单机模式。正在准备今日信号…")
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
        status.set(f"候选 {len(rows)} 条，买入 {buys} 条。数据目录 {output_dir()}")

    def spawn(mode: str, regenerate: bool, label: str, open_html: bool = False) -> None:
        if busy["flag"]:
            messagebox.showinfo("请稍候", "已有任务在运行。")
            return
        busy["flag"] = True
        status.set(label)

        def worker() -> None:
            try:
                run_job(mode, regenerate)
                root.after(0, fill_table)
                if open_html:
                    root.after(400, open_panel)
            except Exception as exc:
                logging.exception("job failed")
                root.after(0, lambda: messagebox.showerror("任务失败", f"{exc}\n日志: {log_path()}"))
            finally:
                busy["flag"] = False

        threading.Thread(target=worker, daemon=True).start()

    def open_panel() -> None:
        try:
            path = open_local_panel()
            status.set(f"已打开本地页面：{path}")
        except Exception as exc:
            logging.exception("open panel failed")
            messagebox.showerror("无法打开页面", f"{exc}\n日志: {log_path()}")

    tk.Button(btns, text="打开结果网页", bg=accent, fg="white", relief="flat", padx=12, pady=6, command=open_panel).pack(side="left", padx=(0, 8))
    tk.Button(btns, text="刷新今日信号", bg="#223044", fg=text, relief="flat", padx=12, pady=6, command=lambda: spawn("quick", False, "正在计算今日信号（快速模式）…")).pack(side="left", padx=4)
    tk.Button(btns, text="完整验证 Walk-Forward", bg="#223044", fg=text, relief="flat", padx=12, pady=6, command=lambda: spawn("full", False, "正在 Walk-Forward + 蒙特卡洛（约数分钟）…")).pack(side="left", padx=4)
    tk.Button(btns, text="打开数据目录", bg="#223044", fg=text, relief="flat", padx=12, pady=6, command=lambda: os.startfile(str(output_dir())) if os.name == "nt" else webbrowser.open(output_dir().as_uri())).pack(side="left", padx=4)

    def bootstrap() -> None:
        if (output_dir() / "ideas.csv").exists():
            fill_table()
            return
        spawn("quick", False, "首次启动：正在本机生成演示行情并计算信号，请稍候…", open_html=True)

    root.after(200, bootstrap)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
