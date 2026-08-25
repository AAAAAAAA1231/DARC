from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from ..config import APP_NAME, APP_VERSION, LEAGUES, LEAGUE_ORDER
from ..model.pipeline import Predictor, PredictionResult
from ..names import display_cn
from ..report import format_report


BG = "#0b1c16"
BG_PANEL = "#12261e"
BG_CARD = "#183328"
FG = "#e8f5e9"
FG_DIM = "#9ccc65"
ACCENT = "#d4af37"
RED = "#ef5350"
BLUE = "#42a5f5"
MUTED = "#80cbc4"


def _pick_font() -> tuple[str, str]:
    if sys.platform.startswith("win"):
        return "Microsoft YaHei UI", "Segoe UI"
    if sys.platform == "darwin":
        return "PingFang SC", "Helvetica Neue"
    return "WenQuanYi Micro Hei", "Noto Sans CJK SC"


class PredictorApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_NAME}  v{APP_VERSION}")
        self.geometry("1280x820")
        self.minsize(1100, 720)
        self.configure(bg=BG)
        self.predictor: Predictor | None = None
        self.fixtures: list = []
        self.current: PredictionResult | None = None
        self._ui_font, self._ui_font_alt = _pick_font()
        self._busy = False
        self._build_style()
        self._build_layout()
        self.after(200, self._bootstrap)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(".", background=BG, foreground=FG, fieldbackground=BG_CARD)
        style.configure("TFrame", background=BG)
        style.configure("Panel.TFrame", background=BG_PANEL)
        style.configure("Card.TFrame", background=BG_CARD)
        style.configure("TLabel", background=BG, foreground=FG, font=(self._ui_font, 11))
        style.configure("Title.TLabel", background=BG, foreground=ACCENT, font=(self._ui_font, 18, "bold"))
        style.configure("Sub.TLabel", background=BG, foreground=FG_DIM, font=(self._ui_font, 10))
        style.configure("Panel.TLabel", background=BG_PANEL, foreground=FG, font=(self._ui_font, 11))
        style.configure("Card.TLabel", background=BG_CARD, foreground=FG, font=(self._ui_font, 11))
        style.configure("Head.TLabel", background=BG_CARD, foreground=ACCENT, font=(self._ui_font, 13, "bold"))
        style.configure("TButton", font=(self._ui_font, 11), padding=6)
        style.configure("Accent.TButton", font=(self._ui_font, 12, "bold"), padding=8)
        style.configure(
            "TRadiobutton",
            background=BG_PANEL,
            foreground=FG,
            font=(self._ui_font, 11),
        )
        style.map("TRadiobutton", background=[("active", BG_PANEL)], foreground=[("active", ACCENT)])
        style.configure("TCombobox", fieldbackground=BG_CARD, background=BG_CARD, foreground=FG)
        style.configure("TNotebook", background=BG, tabmargins=[4, 4, 4, 0])
        style.configure("TNotebook.Tab", background=BG_PANEL, foreground=FG, padding=[14, 6], font=(self._ui_font, 11))
        style.map("TNotebook.Tab", background=[("selected", BG_CARD)], foreground=[("selected", ACCENT)])
        style.configure("Vertical.TScrollbar", background=BG_PANEL)

    def _build_layout(self) -> None:
        header = ttk.Frame(self)
        header.pack(fill="x", padx=18, pady=(14, 8))
        ttk.Label(header, text="⚽  " + APP_NAME, style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="西甲 · 德甲 · 意甲    实力 / 伤停 / 主客场 / 历史校准 / 赛前舆情纠偏", style="Sub.TLabel").pack(
            side="left", padx=16
        )
        self.status_var = tk.StringVar(value="正在初始化模型与历史数据…")
        ttk.Label(header, textvariable=self.status_var, style="Sub.TLabel").pack(side="right")

        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=16, pady=8)

        left = ttk.Frame(body, style="Panel.TFrame", width=380)
        left.pack(side="left", fill="y")
        left.pack_propagate(False)

        ttk.Label(left, text="联赛", style="Panel.TLabel").pack(anchor="w", padx=12, pady=(12, 4))
        self.league_var = tk.StringVar(value="laliga")
        league_row = ttk.Frame(left, style="Panel.TFrame")
        league_row.pack(fill="x", padx=12)
        for key in LEAGUE_ORDER:
            ttk.Radiobutton(
                league_row,
                text=LEAGUES[key].name_cn,
                value=key,
                variable=self.league_var,
                command=self._on_league_change,
            ).pack(side="left", padx=4)

        btn_row = ttk.Frame(left, style="Panel.TFrame")
        btn_row.pack(fill="x", padx=12, pady=8)
        ttk.Button(btn_row, text="刷新赛程", command=self._reload_fixtures).pack(side="left")
        ttk.Button(btn_row, text="预测本场", style="Accent.TButton", command=self._predict_selected).pack(
            side="right"
        )

        ttk.Label(left, text="近期赛程（双击预测）", style="Panel.TLabel").pack(anchor="w", padx=12, pady=(8, 4))
        list_wrap = ttk.Frame(left, style="Panel.TFrame")
        list_wrap.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self.fx_list = tk.Listbox(
            list_wrap,
            bg=BG_CARD,
            fg=FG,
            selectbackground=ACCENT,
            selectforeground="#1b1b1b",
            font=(self._ui_font, 10),
            relief="flat",
            highlightthickness=0,
        )
        scroll = ttk.Scrollbar(list_wrap, orient="vertical", command=self.fx_list.yview)
        self.fx_list.configure(yscrollcommand=scroll.set)
        self.fx_list.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")
        self.fx_list.bind("<Double-Button-1>", lambda _e: self._predict_selected())

        ttk.Label(left, text="或手动指定对阵", style="Panel.TLabel").pack(anchor="w", padx=12)
        manual = ttk.Frame(left, style="Panel.TFrame")
        manual.pack(fill="x", padx=12, pady=8)
        self.home_var = tk.StringVar()
        self.away_var = tk.StringVar()
        self.home_combo = ttk.Combobox(manual, textvariable=self.home_var, width=16)
        self.away_combo = ttk.Combobox(manual, textvariable=self.away_var, width=16)
        self.home_combo.pack(side="left", padx=(0, 6))
        ttk.Label(manual, text="VS", style="Panel.TLabel").pack(side="left")
        self.away_combo.pack(side="left", padx=(6, 0))
        ttk.Button(left, text="预测手动对阵", command=self._predict_manual).pack(padx=12, pady=(0, 14), anchor="e")

        right = ttk.Frame(body)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))

        self.match_title = ttk.Label(right, text="请选择一场比赛开始推理", style="Title.TLabel")
        self.match_title.pack(anchor="w")
        self.match_sub = ttk.Label(right, text="", style="Sub.TLabel")
        self.match_sub.pack(anchor="w", pady=(0, 8))

        bars = ttk.Frame(right, style="Card.TFrame")
        bars.pack(fill="x", pady=6)
        self.bar_canvas = tk.Canvas(bars, height=92, bg=BG_CARD, highlightthickness=0)
        self.bar_canvas.pack(fill="x", padx=8, pady=8)
        self._draw_bars(0.33, 0.34, 0.33)

        score_row = ttk.Frame(right, style="Card.TFrame")
        score_row.pack(fill="x", pady=6)
        self.lbl_90 = ttk.Label(score_row, text="90分钟：—", style="Head.TLabel")
        self.lbl_90.pack(side="left", padx=12, pady=10)
        self.lbl_final = ttk.Label(score_row, text="最终结果：—", style="Head.TLabel")
        self.lbl_final.pack(side="left", padx=18)
        self.lbl_conf = ttk.Label(score_row, text="置信度：—", style="Card.TLabel")
        self.lbl_conf.pack(side="right", padx=12)

        nb = ttk.Notebook(right)
        nb.pack(fill="both", expand=True, pady=8)
        self.txt_summary = self._make_text_tab(nb, "综合结论")
        self.txt_factors = self._make_text_tab(nb, "因素与纠偏")
        self.txt_news = self._make_text_tab(nb, "网络情报")
        self.txt_report = self._make_text_tab(nb, "完整报告")

        foot = ttk.Frame(self)
        foot.pack(fill="x", padx=16, pady=(0, 12))
        ttk.Button(foot, text="导出报告", command=self._export).pack(side="right")
        ttk.Label(
            foot,
            text="模型仅供研究参考，不构成投注建议。每次预测都会重新拉取赛前舆情并做纠偏。",
            style="Sub.TLabel",
        ).pack(side="left")

    def _make_text_tab(self, nb: ttk.Notebook, title: str) -> tk.Text:
        frame = ttk.Frame(nb, style="Card.TFrame")
        nb.add(frame, text=title)
        text = tk.Text(
            frame,
            bg=BG_CARD,
            fg=FG,
            insertbackground=FG,
            font=(self._ui_font, 11),
            wrap="word",
            relief="flat",
            highlightthickness=0,
            padx=10,
            pady=10,
        )
        vs = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=vs.set)
        text.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        return text

    def _set_text(self, widget: tk.Text, content: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", content)
        widget.configure(state="disabled")

    def _draw_bars(self, h: float, d: float, a: float) -> None:
        c = self.bar_canvas
        c.delete("all")
        width = max(c.winfo_width(), 640)
        labels = [("主胜", h, ACCENT), ("平局", d, MUTED), ("客胜", a, BLUE)]
        y = 8
        for name, p, color in labels:
            c.create_text(8, y + 10, text=f"{name}  {p:.1%}", fill=FG, font=(self._ui_font, 11), anchor="w")
            c.create_rectangle(110, y + 2, 110 + int((width - 140) * p), y + 20, fill=color, outline="")
            y += 28

    def _bootstrap(self) -> None:
        def work():
            pred = Predictor()
            try:
                pred.build(progress=lambda m: self.after(0, lambda msg=m: self.status_var.set(msg)))
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror(APP_NAME, f"模型初始化失败：{exc}"))
                return
            self.predictor = pred
            self.after(0, self._after_boot)

        threading.Thread(target=work, daemon=True).start()

    def _after_boot(self) -> None:
        self.status_var.set("模型就绪，正在拉取近期赛程…")
        self._fill_teams()
        self._reload_fixtures()

    def _fill_teams(self) -> None:
        if not self.predictor:
            return
        key = self.league_var.get()
        eng = self.predictor.engines.get(key)
        if not eng:
            return
        labels = [f"{display_cn(t)}  ({t})" for t in eng.teams]
        self.home_combo["values"] = labels
        self.away_combo["values"] = labels

    def _on_league_change(self) -> None:
        self._fill_teams()
        self._reload_fixtures()

    def _reload_fixtures(self) -> None:
        if not self.predictor or self._busy:
            return

        def work():
            try:
                items = self.predictor.upcoming(self.league_var.get())
            except Exception as exc:
                self.after(0, lambda: self.status_var.set(f"赛程获取失败：{exc}"))
                return
            self.fixtures = items
            self.after(0, self._populate_list)

        self.status_var.set("正在从网络刷新赛程…")
        threading.Thread(target=work, daemon=True).start()

    def _populate_list(self) -> None:
        self.fx_list.delete(0, "end")
        if not self.fixtures:
            self.fx_list.insert("end", "暂无赛程（可手动选择对阵）")
            self.status_var.set("未拉到赛程，可手动预测")
            return
        for fx in self.fixtures:
            flag = "✓" if fx.status == "post" else "·"
            self.fx_list.insert("end", f"{flag} {fx.label}")
        self.fx_list.selection_set(0)
        self.status_var.set(f"已载入 {len(self.fixtures)} 场 {LEAGUES[self.league_var.get()].name_cn} 赛程")

    def _selected_fixture(self):
        sel = self.fx_list.curselection()
        if not sel or not self.fixtures:
            return None
        idx = int(sel[0])
        if idx >= len(self.fixtures):
            return None
        return self.fixtures[idx]

    def _predict_selected(self) -> None:
        fx = self._selected_fixture()
        if not fx:
            messagebox.showinfo(APP_NAME, "请先在左侧选择一场比赛")
            return
        self._run_predict(lambda: self.predictor.predict_fixture(fx, progress=self._ui_progress))

    def _parse_combo(self, value: str) -> str:
        value = value.strip()
        if "  (" in value and value.endswith(")"):
            return value.rsplit("  (", 1)[1][:-1]
        return value

    def _predict_manual(self) -> None:
        home = self._parse_combo(self.home_var.get())
        away = self._parse_combo(self.away_var.get())
        if not home or not away:
            messagebox.showinfo(APP_NAME, "请选择主队和客队")
            return
        if home == away:
            messagebox.showinfo(APP_NAME, "主客队不能相同")
            return
        league = self.league_var.get()
        self._run_predict(lambda: self.predictor.predict(league, home, away, progress=self._ui_progress))

    def _ui_progress(self, msg: str) -> None:
        self.after(0, lambda m=msg: self.status_var.set(m))

    def _run_predict(self, fn) -> None:
        if not self.predictor:
            messagebox.showinfo(APP_NAME, "模型尚未就绪")
            return
        if self._busy:
            return
        self._busy = True
        self.status_var.set("正在综合历史模型与赛前网络情报…")

        def work():
            try:
                result = fn()
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror(APP_NAME, f"预测失败：{exc}"))
                self.after(0, lambda: setattr(self, "_busy", False))
                return
            self.after(0, lambda: self._render(result))

        threading.Thread(target=work, daemon=True).start()

    def _render(self, result: PredictionResult) -> None:
        self._busy = False
        self.current = result
        self.match_title.configure(text=f"{result.home_cn}  vs  {result.away_cn}")
        self.match_sub.configure(
            text=f"{result.league_cn}    {result.kickoff}    {result.venue or ''}    期望进球 {result.xg_home:.2f}-{result.xg_away:.2f}"
        )
        self._draw_bars(result.p_home, result.p_draw, result.p_away)
        self.lbl_90.configure(text=f"90分钟：{result.pred_1x2_90}   {result.pred_score_90}")
        self.lbl_final.configure(text=f"最终结果：{result.final_1x2}   {result.final_score}")
        self.lbl_conf.configure(
            text=f"置信度 {result.confidence:.0%}    回测命中 {result.historical_accuracy:.1%}"
        )
        summary = [
            f"90 分钟胜平负：主胜 {result.p_home:.1%}  /  平局 {result.p_draw:.1%}  /  客胜 {result.p_away:.1%}",
            f"90 分钟比分（最大后验）：{result.pred_score_90}",
            f"最终结果：{result.final_1x2}  {result.final_score}",
            "",
            result.final_note,
            "",
            "候选比分：",
        ]
        for s, p in result.top_scores:
            summary.append(f"  {s}   {p:.1%}")
        self._set_text(self.txt_summary, "\n".join(summary))
        fac_lines = result.steps + [""] + [f"· {x}" for x in result.factors]
        if result.adjustments:
            fac_lines += ["", "数值纠偏："]
            for a in result.adjustments:
                fac_lines.append(f"  [{a.factor}] {a.target} {a.delta:+.2%}  {a.reason}")
        self._set_text(self.txt_factors, "\n".join(fac_lines))
        news_lines = []
        if result.injuries:
            news_lines.append("伤停：")
            for inj in result.injuries:
                news_lines.append(f"  · {inj.player}（{inj.team}）{inj.status} {inj.detail}")
            news_lines.append("")
        news_lines.append(f"天气：{result.weather}")
        news_lines.append("")
        news_lines.append("舆情：")
        if result.news:
            for n in result.news:
                news_lines.append(f"  · [{n.source}] {n.title}")
                if n.summary:
                    news_lines.append(f"      {n.summary[:160]}")
        else:
            news_lines.append("  （未检索到强相关新闻，已跳过舆情项）")
        self._set_text(self.txt_news, "\n".join(news_lines))
        self._set_text(self.txt_report, format_report(result))
        self.status_var.set(f"完成：{result.home_cn} vs {result.away_cn}  →  {result.final_1x2} {result.final_score}")
        self.bar_canvas.after(50, lambda: self._draw_bars(result.p_home, result.p_draw, result.p_away))

    def _export(self) -> None:
        if not self.current:
            messagebox.showinfo(APP_NAME, "还没有可导出的预测")
            return
        default = f"{self.current.home_cn}vs{self.current.away_cn}_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        path = filedialog.asksaveasfilename(
            title="导出报告",
            defaultextension=".txt",
            initialfile=default,
            filetypes=[("文本文件", "*.txt")],
        )
        if not path:
            return
        Path(path).write_text(format_report(self.current), encoding="utf-8")
        messagebox.showinfo(APP_NAME, "已导出")


def main() -> None:
    app = PredictorApp()
    app.mainloop()
