"""Standalone HTML panel so the EXE never depends on 127.0.0.1."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .paper.simulator import DISCLAIMER
from .paths import output_dir


def _pct(v) -> str:
    try:
        return f"{float(v) * 100:.1f}%"
    except (TypeError, ValueError):
        return ""


def _num(v, digits: int = 3) -> str:
    try:
        return f"{float(v):.{digits}f}"
    except (TypeError, ValueError):
        return str(v or "")


def write_panel_html(out: Path | None = None, ideas: list[dict] | None = None, snap: dict | None = None) -> Path:
    out = Path(out) if out else output_dir()
    out.mkdir(parents=True, exist_ok=True)
    if snap is None:
        sp = out / "snapshot.json"
        snap = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else {}
    if ideas is None:
        import pandas as pd

        csv_path = out / "ideas.csv"
        if csv_path.exists():
            df = pd.read_csv(csv_path, dtype={"symbol": str})
            if "symbol" in df.columns:
                df["symbol"] = df["symbol"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(6)
            ideas = df.fillna("").to_dict(orient="records")
        else:
            ideas = []

    wf = snap.get("walkforward") or {}
    mc = snap.get("monte_carlo") or {}
    weights = snap.get("weights") or {}
    rows_html = []
    for r in ideas:
        action = html.escape(str(r.get("action") or ""))
        rows_html.append(
            "<tr class='{a}'><td>{sym}</td><td>{name}</td><td>{board}</td>"
            "<td>{score}</td><td><span class='tag {a}'>{action}</span></td>"
            "<td>{shares}</td><td>{sl}</td><td>{tp}</td>"
            "<td>{p10}</td><td>{p50}</td><td>{p90}</td><td class='flags'>{flags}</td></tr>".format(
                a=action,
                sym=html.escape(str(r.get("symbol") or "")),
                name=html.escape(str(r.get("name") or "")),
                board=html.escape(str(r.get("board_cn") or r.get("board") or "")),
                score=_num(r.get("score")),
                action=action,
                shares=html.escape(str(r.get("shares") or "")),
                sl=html.escape(str(r.get("stop_loss") or "")),
                tp=html.escape(str(r.get("take_profit") or "")),
                p10=_pct(r.get("ci_p10")),
                p50=_pct(r.get("ci_p50")),
                p90=_pct(r.get("ci_p90")),
                flags=html.escape(str(r.get("flags") or "")),
            )
        )
    if not rows_html:
        rows_html.append("<tr><td colspan='12'>暂无候选。请在程序窗口点击「刷新今日信号」。</td></tr>")

    weight_html = []
    for k, v in weights.items():
        try:
            pct = float(v) * 100
        except (TypeError, ValueError):
            pct = 0.0
        weight_html.append(
            f"<div class='w'><label>{html.escape(str(k))}</label>"
            f"<div class='bar'><i style='width:{pct:.1f}%'></i></div>"
            f"<em>{pct:.1f}%</em></div>"
        )
    if not weight_html:
        weight_html.append("<p class='muted'>运行信号后显示方法权重。</p>")

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>A股量化辅助 · 本机结果</title>
<style>
body{{margin:0 auto;max-width:1180px;padding:28px 20px;background:#0b1017;color:#e7eef8;font-family:"Microsoft YaHei UI",sans-serif}}
h1{{margin:0}} .sub,.muted{{color:#8b9bb0}}
.disclaimer{{margin:18px 0;padding:14px;background:#241a12;border:1px solid #5c431d;border-radius:10px;color:#f0d5a6}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}
.kpis article{{background:#141c27;border:1px solid #243044;border-radius:12px;padding:12px}}
.kpis span{{display:block;color:#8b9bb0;font-size:12px}}
.card{{background:#141c27;border:1px solid #243044;border-radius:14px;padding:16px;margin:14px 0}}
.w{{display:grid;grid-template-columns:140px 1fr 52px;gap:8px;align-items:center;margin:6px 0}}
.bar{{height:8px;background:#223044;border-radius:99px;overflow:hidden}}
.bar i{{display:block;height:100%;background:#3d8bfd}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th,td{{padding:8px;border-bottom:1px solid #243044;text-align:left;white-space:nowrap}}
.tag{{padding:2px 8px;border-radius:999px}}
.tag.buy{{background:#16351f;color:#3fb950}}
.tag.exit{{background:#3d1515;color:#f85149}}
.tag.no_trade,.tag.hold{{background:#243044;color:#8b9bb0}}
.flags{{white-space:normal;color:#8b9bb0;max-width:240px}}
</style>
</head>
<body>
<h1>A股量化辅助系统</h1>
<p class="sub">单机结果页（本地 HTML 文件） · 实时行情 · T+1 · 非实盘</p>
<section class="disclaimer">{html.escape(str(snap.get("disclaimer") or DISCLAIMER))}</section>
<p class="muted">{html.escape(str(snap.get("quote_note") or ""))}</p>
<section class="kpis">
<article><span>信号日</span><strong>{html.escape(str(snap.get("asof") or "尚未运行"))}</strong></article>
<article><span>行情时刻</span><strong>{html.escape(str(snap.get("quote_time") or "-"))}</strong></article>
<article><span>数据来源</span><strong>{html.escape(str(snap.get("data_source_cn") or snap.get("data_source") or "-"))}</strong></article>
<article><span>分层股票池</span><strong>{html.escape(str(snap.get("universe_selected") or 0))}</strong></article>
<article><span>买入候选</span><strong>{html.escape(str(snap.get("n_buy") or 0))}</strong></article>
<article><span>OOS 回撤</span><strong>{_pct(wf.get("max_drawdown"))}</strong></article>
<article><span>OOS Sharpe</span><strong>{_num(wf.get("sharpe"), 2)}</strong></article>
<article><span>MC 回撤预警</span><strong>{_pct(mc.get("p_dd_worse_than_alert"))}</strong></article>
</section>
<section class="card"><h2>方法动态权重</h2>{"".join(weight_html)}</section>
<section class="card">
<h2>T日收盘候选 · ATR 止盈止损 · 置信区间</h2>
<table>
<thead><tr><th>代码</th><th>名称</th><th>板块</th><th>分值</th><th>动作</th><th>股数</th><th>止损</th><th>止盈</th><th>P10</th><th>P50</th><th>P90</th><th>备注</th></tr></thead>
<tbody>{"".join(rows_html)}</tbody>
</table>
</section>
</body></html>
"""
    path = out / "panel.html"
    path.write_text(page, encoding="utf-8")
    return path
