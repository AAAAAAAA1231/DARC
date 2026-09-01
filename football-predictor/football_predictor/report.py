from __future__ import annotations

from .model.pipeline import PredictionResult


def format_report(result: PredictionResult) -> str:
    lines = [
        "═" * 56,
        f"{result.league_cn} 胜负推理报告",
        f"{result.home_cn}  vs  {result.away_cn}",
        f"开球：{result.kickoff}    场地：{result.venue or '—'}",
        "═" * 56,
        "",
        "【90 分钟内（含补时）】",
        f"  主胜 {result.p_home:5.1%}    平局 {result.p_draw:5.1%}    客胜 {result.p_away:5.1%}",
        f"  预测赛果：{result.pred_1x2_90}",
        f"  最可能比分：{result.pred_score_90}",
        f"  期望进球：{result.xg_home:.2f} - {result.xg_away:.2f}",
        "",
        "【最终结果】",
        f"  {result.final_1x2}   比分 {result.final_score}",
        f"  {result.final_note}",
        "",
        f"【置信度】{result.confidence:.0%}    历史回测 1X2 命中率 {result.historical_accuracy:.1%}",
        "",
        "【候选比分】",
    ]
    for score, p in result.top_scores:
        lines.append(f"  {score:5}  {p:5.1%}")
    if result.market:
        lines += [
            "",
            "【市场隐含概率】",
            f"  主胜 {result.market[0]:.1%}  平 {result.market[1]:.1%}  客胜 {result.market[2]:.1%}",
        ]
    lines += ["", "【纠偏步骤】"]
    for step in result.steps:
        lines.append(f"  · {step}")
    lines += ["", "【综合考虑因素】"]
    for fac in result.factors:
        lines.append(f"  · {fac}")
    if result.injuries:
        lines += ["", "【伤停名单】"]
        for inj in result.injuries:
            lines.append(f"  · [{inj.team}] {inj.player} — {inj.status} {inj.detail}".rstrip())
    if result.news:
        lines += ["", "【赛前网络情报】"]
        for n in result.news[:10]:
            lines.append(f"  · {n.source}: {n.title}")
    lines += ["", f"天气：{result.weather}", "═" * 56]
    return "\n".join(lines)
