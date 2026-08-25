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
        self.geometry("1080x680")
        self.minsize(900, 560)
        self.configure(bg=BG)
        self.predictor = Predictor()
        self.results: list[PredictionResult] = []
        self.ui_font = _font()
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

        tk.Label(self, text=APP_NAME, bg=BG, fg=ACCENT, font=(self.ui_font, 22, "bold")).pack(pady=(16, 4))
        tk.Label(
            self,
            text="打开后自动联网计算西甲 / 德甲 / 意甲 近期未赛场次（实力 · 伤停 · 主客场 · 舆情纠偏）",
            bg=BG,
            fg=MUTED,
            font=(self.ui_font, 11),
        ).pack()

        self.status = tk.StringVar(value="正在联网，请稍候…")
        tk.Label(self, textvariable=self.status, bg=BG, fg="#fff59d", font=(self.ui_font, 13)).pack(pady=10)

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

        tk.Button(self, text="重新联网预测", command=self._start, bg=ACCENT, fg="#1b1b1b", font=(self.ui_font, 12, "bold"), relief="flat", padx=16, pady=6).pack(pady=(4, 14))
        tk.Label(self, text=f"v{APP_VERSION}  仅供观赛参考，不是投注建议", bg=BG, fg="#689f38", font=(self.ui_font, 9)).pack(pady=(0, 10))

    def _start(self) -> None:
        self.status.set("正在联网，请稍候…")
        for item in self.tree.get_children():
            self.tree.delete(item)
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self) -> None:
        try:
            if not self.predictor.ready():
                self.predictor.build(progress=lambda m: self.after(0, lambda msg=m: self.status.set(msg)))
            self.after(0, lambda: self.status.set("正在拉取近期赛程并逐场纠偏…"))
            results = self.predictor.predict_all_upcoming(
                progress=lambda m: self.after(0, lambda msg=m: self.status.set(msg))
            )
            self.after(0, lambda: self._show(results))
        except Exception as exc:
            self.after(0, lambda: self.status.set(f"失败：{exc}。请确认已联网后点「重新联网预测」。"))

    def _show(self, results: list[PredictionResult]) -> None:
        self.results = results
        for item in self.tree.get_children():
            self.tree.delete(item)
        if not results:
            self.status.set("没有找到近期未赛场次，请稍后重试。")
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
        self.status.set(f"完成 {len(results)} 场  {now}    可关闭窗口，或再点一次重新预测")


def main() -> None:
    PredictorApp().mainloop()
