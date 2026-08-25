from __future__ import annotations

from datetime import datetime
import sys
import threading
import tkinter as tk
from tkinter import ttk

from ..config import APP_NAME, APP_VERSION
from ..model.pipeline import Predictor, PredictionResult


BG = "#0b1c16"
BG_CARD = "#163328"
FG = "#f1f8e9"
ACCENT = "#d4af37"
MUTED = "#a5d6a7"


def _font() -> str:
    if sys.platform.startswith("win"):
        return "Microsoft YaHei UI"
    if sys.platform == "darwin":
        return "PingFang SC"
    return "WenQuanYi Micro Hei"


class PredictorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_NAME)
        self.geometry("1100x720")
        self.minsize(920, 600)
        self.configure(bg=BG)
        self.predictor = Predictor()
        self.results: list[PredictionResult] = []
        self.ui_font = _font()
        self._busy = False
        self._build()
        self.after(300, self._start)

    def _build(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Treeview", background=BG_CARD, fieldbackground=BG_CARD, foreground=FG, rowheight=32, font=(self.ui_font, 11))
        style.configure("Treeview.Heading", background="#0f2a20", foreground=ACCENT, font=(self.ui_font, 11, "bold"))
        style.map("Treeview", background=[("selected", "#2e7d32")], foreground=[("selected", "white")])
        style.configure("TButton", font=(self.ui_font, 12), padding=8)

        tk.Label(self, text=APP_NAME, bg=BG, fg=ACCENT, font=(self.ui_font, 22, "bold")).pack(pady=(16, 2))
        tk.Label(
            self,
            text="打开后自动预测近期未赛  ·  也可搜索：下一场皇马　巴萨vs马竞　德甲　尤文",
            bg=BG,
            fg=MUTED,
            font=(self.ui_font, 11),
        ).pack()

        search_row = tk.Frame(self, bg=BG)
        search_row.pack(fill="x", padx=16, pady=(12, 4))
        self.search_var = tk.StringVar()
        entry = tk.Entry(
            search_row,
            textvariable=self.search_var,
            font=(self.ui_font, 13),
            bg=BG_CARD,
            fg=FG,
            insertbackground=FG,
            relief="flat",
        )
        entry.pack(side="left", fill="x", expand=True, ipady=8, padx=(0, 8))
        entry.bind("<Return>", lambda _e: self._search())
        tk.Button(
            search_row,
            text="搜索预测",
            command=self._search,
            bg=ACCENT,
            fg="#1b1b1b",
            font=(self.ui_font, 12, "bold"),
            relief="flat",
            padx=18,
            pady=6,
        ).pack(side="left")
        self.search_entry = entry

        self.status = tk.StringVar(value="正在联网，请稍候…")
        tk.Label(self, textvariable=self.status, bg=BG, fg="#fff59d", font=(self.ui_font, 13)).pack(pady=8)

        cols = ("league", "kickoff", "match", "r90", "final", "score", "probs", "conf")
        wrap = tk.Frame(self, bg=BG)
        wrap.pack(fill="both", expand=True, padx=16, pady=8)
        self.tree = ttk.Treeview(wrap, columns=cols, show="headings", selectmode="browse")
        headers = {
            "league": "联赛",
            "kickoff": "开球",
            "match": "对阵（主 vs 客）",
            "r90": "90分钟",
            "final": "最终结果",
            "score": "比分",
            "probs": "主胜 / 平 / 客胜",
            "conf": "把握",
        }
        widths = {"league": 70, "kickoff": 130, "match": 240, "r90": 80, "final": 90, "score": 70, "probs": 200, "conf": 70}
        for col in cols:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="center")
        vs = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vs.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")

        btns = tk.Frame(self, bg=BG)
        btns.pack(pady=(4, 12))
        tk.Button(btns, text="显示全部近期", command=self._start, bg="#2e7d32", fg="white", font=(self.ui_font, 12, "bold"), relief="flat", padx=16, pady=6).pack(side="left", padx=6)
        tk.Label(self, text=f"v{APP_VERSION}  仅供观赛参考，不是投注建议", bg=BG, fg="#689f38", font=(self.ui_font, 9)).pack(pady=(0, 10))

    def _ensure_ready(self) -> None:
        if not self.predictor.ready():
            self.predictor.build(progress=lambda m: self.after(0, lambda msg=m: self.status.set(msg)))

    def _start(self) -> None:
        if self._busy:
            return
        self._busy = True
        self.status.set("正在联网，请稍候…")
        self._clear_table()
        threading.Thread(target=self._work_all, daemon=True).start()

    def _search(self) -> None:
        q = self.search_var.get().strip()
        if not q:
            self.status.set("请输入：下一场皇马 / 巴萨vs马竞 / 德甲")
            return
        if self._busy:
            return
        self._busy = True
        self.status.set(f"正在搜索「{q}」…")
        threading.Thread(target=self._work_search, args=(q,), daemon=True).start()

    def _work_all(self) -> None:
        try:
            self._ensure_ready()
            self.after(0, lambda: self.status.set("正在拉取近期赛程并逐场纠偏…"))
            results = self.predictor.predict_all_upcoming(
                progress=lambda m: self.after(0, lambda msg=m: self.status.set(msg))
            )
            self.after(0, lambda: self._show(results, done_text=None))
        except Exception as exc:
            self.after(0, lambda: self.status.set(f"失败：{exc}。请确认已联网后重试。"))
            self.after(0, lambda: setattr(self, "_busy", False))

    def _work_search(self, q: str) -> None:
        try:
            self._ensure_ready()
            msg, results = self.predictor.predict_search(
                q, progress=lambda m: self.after(0, lambda txt=m: self.status.set(txt))
            )
            self.after(0, lambda: self._show(results, done_text=msg))
        except Exception as exc:
            self.after(0, lambda: self.status.set(f"搜索失败：{exc}"))
            self.after(0, lambda: setattr(self, "_busy", False))

    def _clear_table(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)

    def _show(self, results: list[PredictionResult], done_text: str | None) -> None:
        self._busy = False
        self.results = results
        self._clear_table()
        if not results:
            self.status.set(done_text or "没有找到近期未赛场次，请换个关键词。")
            return
        for r in results:
            self.tree.insert(
                "",
                "end",
                values=(
                    r.league_cn,
                    r.kickoff,
                    f"{r.home_cn} vs {r.away_cn}",
                    r.pred_1x2_90,
                    r.final_1x2,
                    r.final_score,
                    f"{r.p_home:.0%} / {r.p_draw:.0%} / {r.p_away:.0%}",
                    f"{r.confidence:.0%}",
                ),
            )
        now = datetime.now().strftime("%H:%M")
        self.status.set((done_text or f"完成 {len(results)} 场") + f"  {now}")


def main() -> None:
    PredictorApp().mainloop()
