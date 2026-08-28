"""Local HTML report so results can be reviewed without Tk."""

from __future__ import annotations

from html import escape
from pathlib import Path

from .advice import ACTION_FLAT, ACTION_LONG, ACTION_SHORT
from .engine import Report

COLORS = {
    ACTION_LONG: "#3dd68c",
    ACTION_SHORT: "#ff6b6b",
    ACTION_FLAT: "#e6c35c",
}


def render_html(report: Report) -> str:
    cards = []
    for item in report.items:
        color = COLORS[item.action]
        chg = "—" if item.change_pct is None else f"{item.change_pct:+.2f}%"
        spot = "—" if item.spot is None else f"{item.spot:.2f}"
        reasons = "".join(f"<li>{escape(row)}</li>" for row in item.reasons)
        rows = ""
        if item.stocks:
            body = "".join(
                "<tr>"
                f"<td>{escape(stock.symbol)}</td>"
                f"<td>{escape(stock.index_name)}</td>"
                f"<td>{'—' if stock.spot is None else f'{stock.spot:.2f}'}</td>"
                f"<td>{'—' if stock.change_pct is None else f'{stock.change_pct:+.2f}%'}</td>"
                f"<td style='color:{COLORS[stock.action]}'>{escape(stock.action)}</td>"
                f"<td>{stock.size_pct}%</td>"
                f"<td>{stock.expected_return:.3%}</td>"
                f"<td>{stock.p_up:.1%}</td>"
                f"<td>{escape(stock.regime)}</td>"
                "</tr>"
                for stock in item.stocks
            )
            rows = (
                "<table><thead><tr>"
                "<th>代码</th><th>名称</th><th>现价</th><th>涨跌</th><th>建议</th>"
                "<th>仓位</th><th>E[r]</th><th>P(up)</th><th>状态</th>"
                f"</tr></thead><tbody>{body}</tbody></table>"
            )
        cards.append(
            f"""
<article class="card">
  <header>
    <h2>{escape(item.market_name)} <span>{escape(item.exchange)}</span></h2>
    <p class="action" style="color:{color}">{escape(item.action)} · 仓位 {item.size_pct}%</p>
  </header>
  <p class="meta">{escape(item.index_name)} · 现价 {escape(spot)} {escape(chg)} ·
     {escape(item.regime)}/{escape(item.session)} · 收盘 {item.last_close:.2f}（{escape(item.last_date)}） · 源 {escape(item.data_source)}</p>
  <p class="stats">100亿极限 E[r]={item.expected_return:.3%} &nbsp; P(up)={item.p_up:.1%} &nbsp;
     P5/P50/P95={item.p05:.3%}/{item.p50:.3%}/{item.p95:.3%} &nbsp; 核验偏差 {item.verify_error:.2e}</p>
  <ul>{reasons}</ul>
  {rows}
</article>
"""
        )
    errors = ""
    if report.errors:
        errors = "<pre class='err'>" + escape("\n".join(report.errors)) + "</pre>"
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>开盘建议</title>
<style>
  body {{ background:#10141c; color:#e8eef7; font-family:"Segoe UI","Microsoft YaHei",sans-serif; margin:0; padding:24px; }}
  h1 {{ font-size:28px; margin:0 0 8px; }}
  .sub {{ color:#93a0b5; margin-bottom:20px; }}
  .card {{ background:#1b2230; border:1px solid #2c3648; border-radius:12px; padding:16px 20px; margin:0 0 14px; }}
  .card h2 {{ margin:0; font-size:18px; }}
  .card h2 span {{ color:#93a0b5; font-weight:normal; font-size:14px; }}
  .action {{ font-size:20px; font-weight:700; margin:0; }}
  header {{ display:flex; justify-content:space-between; align-items:center; gap:12px; }}
  .meta,.stats {{ color:#93a0b5; font-size:13px; }}
  .stats {{ color:#e8eef7; font-family:Consolas,monospace; }}
  ul {{ margin:8px 0 0; padding-left:18px; color:#93a0b5; }}
  table {{ width:100%; border-collapse:collapse; margin-top:10px; font-size:13px; }}
  th,td {{ text-align:left; padding:6px 8px; border-bottom:1px solid #2c3648; }}
  th {{ color:#93a0b5; font-weight:600; }}
  .foot {{ color:#93a0b5; font-size:12px; margin-top:18px; }}
  .err {{ color:#ff6b6b; }}
</style>
</head>
<body>
<h1>打开时刻个股操作建议</h1>
<p class="sub">打开时刻 {escape(report.opened_at)} · 按交易场所划分 · 建议取值 = 100亿次独立模拟解析极限
  · <a href="/refresh" style="color:#3dd68c">按当前时刻重算</a></p>
{''.join(cards)}
{errors}
<p class="foot">{escape(report.disclaimer)}</p>
</body>
</html>
"""


def write_html(report: Report, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_html(report), encoding="utf-8")
    return path


def render_loading(message: str, failed: bool = False) -> str:
    color = "#ff6b6b" if failed else "#e6c35c"
    poll = "" if failed else """
<script>
async function tick() {
  try {
    const r = await fetch('/status');
    const s = await r.json();
    const el = document.getElementById('msg');
    if (el) el.textContent = s.error || s.message || '计算中';
    if (s.done) location.reload();
  } catch (e) {}
}
setInterval(tick, 1500);
</script>
"""
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8"/>
<title>开盘建议</title>
<style>
  body {{ background:#10141c; color:#e8eef7; font-family:"Segoe UI","Microsoft YaHei",sans-serif;
         margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center; }}
  .box {{ text-align:center; max-width:640px; padding:24px; }}
  h1 {{ margin:0 0 12px; }}
  p {{ color:{color}; font-size:16px; }}
</style>
</head>
<body>
<div class="box">
  <h1>打开时刻个股操作建议</h1>
  <p id="msg">{escape(message)}</p>
  <p style="color:#93a0b5;font-size:13px">按交易场所逐只计算，大约需要几十秒，请不要关闭窗口。</p>
</div>
{poll}
</body>
</html>
"""

