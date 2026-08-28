"""Desktop window: open the EXE, get venue-split advice for that moment."""

from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk
from typing import Callable

from .advice import ACTION_FLAT, ACTION_LONG, ACTION_SHORT, Advice
from .cli import format_text
from .engine import Report, run_report
from .model import DEFAULT_VERIFY_SIMS
from .universe import DEFAULT_PER_MARKET

BG = "#10141c"
CARD = "#1b2230"
FG = "#e8eef7"
MUTED = "#93a0b5"
LINE = "#2c3648"
LONG = "#3dd68c"
FLAT = "#e6c35c"
SHORT = "#ff6b6b"


class AdvisorApp:
    def __init__(
        self,
        n_verify: int = DEFAULT_VERIFY_SIMS,
        seed: int | None = 20260828,
        per_market: int = DEFAULT_PER_MARKET,
    ) -> None:
        self.n_verify = n_verify
        self.seed = seed
        self.per_market = per_market
        self.root = tk.Tk()
        self.root.title("开盘建议 · 按交易场所")
        self.root.geometry("1100x780")
        self.root.minsize(900, 640)
        self.root.configure(bg=BG)
        self.status = tk.StringVar(value="正在根据打开时刻拉取行情并拟合模型…")
        self._build()
        self.root.after(120, self.refresh)

    def _build(self) -> None:
        header = tk.Frame(self.root, bg=BG)
        header.pack(fill="x", padx=20, pady=(16, 8))
        tk.Label(
            header,
            text="打开时刻个股操作建议",
            font=("Microsoft YaHei UI", 20, "bold"),
            fg=FG,
            bg=BG,
        ).pack(side="left")
        ttk.Button(header, text="按当前时刻重算", command=self.refresh).pack(side="right")

        tk.Label(
            self.root,
            textvariable=self.status,
            font=("Microsoft YaHei UI", 10),
            fg=MUTED,
            bg=BG,
            anchor="w",
            justify="left",
            wraplength=1040,
        ).pack(fill="x", padx=20)

        canvas_host = tk.Frame(self.root, bg=BG)
        canvas_host.pack(fill="both", expand=True, padx=12, pady=8)
        self.canvas = tk.Canvas(canvas_host, bg=BG, highlightthickness=0)
        scroll = ttk.Scrollbar(canvas_host, orient="vertical", command=self.canvas.yview)
        self.cards = tk.Frame(self.canvas, bg=BG)
        self.cards.bind(
            "<Configure>",
            lambda _e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.cards, anchor="nw")
        self.canvas.configure(yscrollcommand=scroll.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.canvas.bind_all("<MouseWheel>", lambda e: self.canvas.yview_scroll(int(-e.delta / 120), "units"))

        self.disclaimer = tk.Label(
            self.root,
            text="",
            font=("Microsoft YaHei UI", 8),
            fg=MUTED,
            bg=BG,
            wraplength=1040,
            justify="left",
            anchor="w",
        )
        self.disclaimer.pack(fill="x", padx=20, pady=(0, 12))

    def refresh(self) -> None:
        self.status.set("正在拉取公开行情、拟合模型，并计算 100 亿次模拟极限…")
        for child in self.cards.winfo_children():
            child.destroy()

        def work() -> None:
            try:
                report = run_report(
                    n_verify=self.n_verify,
                    seed=self.seed,
                    per_market=self.per_market,
                    progress=lambda msg: self.root.after(0, lambda m=msg: self.status.set(m)),
                )
                self.root.after(0, lambda: self._render(report))
            except Exception as exc:  # noqa: BLE001 — show in the window
                self.root.after(0, lambda: self.status.set(f"失败：{exc}"))

        threading.Thread(target=work, daemon=True).start()

    def _render(self, report: Report) -> None:
        self.status.set(
            f"打开时刻 {report.opened_at}  ·  建议取值 = 100亿次独立模拟解析极限  ·  "
            f"个股 {sum(len(item.stocks) for item in report.items)} 只"
        )
        self.disclaimer.configure(text=report.disclaimer)
        for item in report.items:
            self._card(item)
        if report.errors:
            err = tk.Label(
                self.cards,
                text="部分场所失败：\n" + "\n".join(report.errors),
                fg=SHORT,
                bg=BG,
                justify="left",
                anchor="w",
                font=("Microsoft YaHei UI", 9),
            )
            err.pack(fill="x", padx=8, pady=8)

    def _card(self, item: Advice) -> None:
        color = {ACTION_LONG: LONG, ACTION_SHORT: SHORT, ACTION_FLAT: FLAT}[item.action]
        box = tk.Frame(self.cards, bg=CARD, highlightbackground=LINE, highlightthickness=1)
        box.pack(fill="x", padx=8, pady=6)
        top = tk.Frame(box, bg=CARD)
        top.pack(fill="x", padx=14, pady=(12, 4))
        tk.Label(
            top,
            text=f"{item.market_name}  ·  {item.exchange}",
            font=("Microsoft YaHei UI", 13, "bold"),
            fg=FG,
            bg=CARD,
        ).pack(side="left")
        tk.Label(
            top,
            text=f"{item.action}   仓位 {item.size_pct}%",
            font=("Microsoft YaHei UI", 13, "bold"),
            fg=color,
            bg=CARD,
        ).pack(side="right")
        chg = "—" if item.change_pct is None else f"{item.change_pct:+.2f}%"
        spot = "—" if item.spot is None else f"{item.spot:.2f}"
        tk.Label(
            box,
            text=(
                f"{item.index_name}  现价 {spot}  {chg}  状态 {item.regime}/{item.session}  "
                f"收盘 {item.last_close:.2f}（{item.last_date}）  源 {item.data_source}"
            ),
            font=("Microsoft YaHei UI", 9),
            fg=MUTED,
            bg=CARD,
            anchor="w",
        ).pack(fill="x", padx=14)
        tk.Label(
            box,
            text=(
                f"100亿极限  E[r]={item.expected_return:.3%}   P(up)={item.p_up:.1%}   "
                f"P5/P50/P95={item.p05:.3%}/{item.p50:.3%}/{item.p95:.3%}   "
                f"核验偏差 {item.verify_error:.2e}"
            ),
            font=("Consolas", 9),
            fg=FG,
            bg=CARD,
            anchor="w",
        ).pack(fill="x", padx=14, pady=(4, 2))
        tk.Label(
            box,
            text="\n".join(f"· {row}" for row in item.reasons),
            font=("Microsoft YaHei UI", 9),
            fg=MUTED,
            bg=CARD,
            justify="left",
            anchor="w",
            wraplength=1000,
        ).pack(fill="x", padx=14, pady=(0, 8))
        if item.stocks:
            self._stock_table(box, item.stocks)

    def _stock_table(self, parent: tk.Frame, stocks: list[Advice]) -> None:
        head = tk.Frame(parent, bg=CARD)
        head.pack(fill="x", padx=14, pady=(4, 2))
        cols = ("代码", "名称", "现价", "涨跌", "建议", "仓位", "E[r]", "P(up)", "状态")
        widths = (70, 90, 80, 70, 50, 50, 80, 70, 50)
        for text, width in zip(cols, widths):
            tk.Label(head, text=text, width=width // 8, anchor="w", fg=MUTED, bg=CARD, font=("Microsoft YaHei UI", 8)).pack(
                side="left"
            )
        for stock in stocks:
            row = tk.Frame(parent, bg=CARD)
            row.pack(fill="x", padx=14)
            color = {ACTION_LONG: LONG, ACTION_SHORT: SHORT, ACTION_FLAT: FLAT}[stock.action]
            chg = "—" if stock.change_pct is None else f"{stock.change_pct:+.2f}%"
            spot = "—" if stock.spot is None else f"{stock.spot:.2f}"
            values = (
                stock.symbol,
                stock.index_name[:8],
                spot,
                chg,
                stock.action,
                f"{stock.size_pct}%",
                f"{stock.expected_return:.2%}",
                f"{stock.p_up:.0%}",
                stock.regime,
            )
            for i, (text, width) in enumerate(zip(values, widths)):
                fg = color if i == 4 else FG
                tk.Label(
                    row,
                    text=text,
                    width=width // 8,
                    anchor="w",
                    fg=fg,
                    bg=CARD,
                    font=("Consolas" if i != 1 else "Microsoft YaHei UI", 9),
                ).pack(side="left")
        tk.Frame(parent, bg=CARD, height=10).pack(fill="x")


def run_gui(
    n_verify: int = DEFAULT_VERIFY_SIMS,
    seed: int | None = 20260828,
    per_market: int = DEFAULT_PER_MARKET,
) -> None:
    app = AdvisorApp(n_verify=n_verify, seed=seed, per_market=per_market)
    app.root.mainloop()


def save_text_report(path: str, report: Report) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(format_text(report))


Progress = Callable[[str], None]
