"""Markdown + chart artifacts for a pipeline run."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def _plot_equity(series: pd.Series, path: Path, title: str) -> None:
    if series is None or series.empty:
        return
    fig, ax = plt.subplots(figsize=(9.5, 4.2))
    ax.plot(series.index, series.values, color="#1f6feb", lw=1.6)
    ax.set_title(title)
    ax.set_ylabel("NAV")
    ax.grid(True, alpha=0.3)
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _plot_mc(dist: pd.DataFrame, path: Path) -> None:
    use = dist[dist.get("source", "return_bootstrap") == "return_bootstrap"] if "source" in dist.columns else dist
    if use.empty or "max_drawdown" not in use:
        return
    fig, axes = plt.subplots(1, 2, figsize=(9.5, 3.8))
    axes[0].hist(use["total_return"].dropna(), bins=18, color="#3fb950", alpha=0.85)
    axes[0].set_title("MC net return")
    axes[1].hist(use["max_drawdown"].dropna(), bins=18, color="#f85149", alpha=0.85)
    axes[1].set_title("MC max drawdown")
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def write_report(out: Path, snapshot: dict, ideas: pd.DataFrame, wf, mc, bt) -> Path:
    _plot_equity(bt.equity, out / "equity.png", "In-sample path (not the delivery metric)")
    _plot_equity(wf.oos_equity, out / "oos_equity.png", "Walk-forward OOS equity (primary)")
    if mc.distribution is not None and not mc.distribution.empty:
        _plot_mc(mc.distribution, out / "monte_carlo.png")

    lines = [
        "# A股量化辅助系统报告",
        "",
        "> 本报告是概率信号与风险控制输出，不是收益承诺，也不能判断全部个股未来走势。",
        "",
        f"- 信号日: **{snapshot.get('asof')}**（收盘后）",
        f"- 选中标的: {snapshot.get('universe_selected')} / 入围 {snapshot.get('universe_eligible')}",
        f"- 买入候选: {snapshot.get('n_buy')}",
        "",
        "## 样本外（Walk-Forward）",
        "",
        "```json",
        __import__("json").dumps(snapshot.get("walkforward", {}), ensure_ascii=False, indent=2, default=str),
        "```",
        "",
        "## 蒙特卡洛摘要",
        "",
        "```json",
        __import__("json").dumps(snapshot.get("monte_carlo", {}), ensure_ascii=False, indent=2, default=str),
        "```",
        "",
        "### 由模拟分布修正的权重/风控",
        "",
        "```json",
        __import__("json").dumps(
            {"ensemble": snapshot.get("adjusted_ensemble"), "risk": snapshot.get("adjusted_risk"), "notes": snapshot.get("mc_notes")},
            ensure_ascii=False,
            indent=2,
            default=str,
        ),
        "```",
        "",
        "## 动态方法权重（最近一次）",
        "",
        "```json",
        __import__("json").dumps(snapshot.get("weights", {}), ensure_ascii=False, indent=2),
        "```",
        "",
        "## 当日候选（含 ATR 止盈止损与收益置信区间）",
        "",
    ]
    if ideas is not None and not ideas.empty:
        show = ideas.head(20)
        cols = [c for c in ["symbol", "name", "board_cn", "score", "action", "shares", "stop_loss", "take_profit", "ci_p10", "ci_p50", "ci_p90", "flags"] if c in show.columns]
        lines.append(_to_md(show[cols]))
    else:
        lines.append("_无候选。_")
    lines += [
        "",
        "## 免责声明",
        "",
        snapshot.get("disclaimer", ""),
        "",
    ]
    path = out / "REPORT.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _to_md(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    header = "| " + " | ".join(str(c) for c in cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    body = []
    for _, row in df.iterrows():
        body.append("| " + " | ".join(_cell(row[c]) for c in cols) + " |")
    return "\n".join([header, sep, *body])


def _cell(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    s = str(v).replace("|", "/")
    if len(s) > 48:
        return s[:45] + "..."
    return s
