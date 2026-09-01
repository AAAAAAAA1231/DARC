from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from typing import Iterable

from .models import ScoredToken, VenuePulse
from .scoring import NEW_CHAINS


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value), quote=True)


def _money(value: float | None) -> str:
    if value is None:
        return "—"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def _pct(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:+.1f}%"


def _age(days: float | None) -> str:
    if days is None:
        return "未知"
    if days < 1:
        return f"{days * 24:.0f} 小时"
    return f"{days:.1f} 天"


def render_text(venues: list[VenuePulse], tokens: list[ScoredToken], generated_at: datetime) -> str:
    lines = [
        f"Fifty-X Radar  {generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        "规则：新场子 + 独占叙事 + 浅开盘；能站住还要有第二支柱。",
        "这不是投资建议。50 倍发生在开盘段，不发生在已经过亿之后。",
        "",
        "== 新场子 ==",
    ]
    hot = [v for v in venues if v.label != "普通场"][:8]
    if not hot:
        lines.append("这一轮没有扫到特别新的链/发射台热度。")
    for venue in hot:
        age = _age(venue.median_age_days)
        samples = ", ".join(venue.sample_symbols) or "—"
        lines.append(
            f"- [{venue.label}] {venue.chain}/{venue.dex}  "
            f"成交 {_money(venue.volume_h24)}  样本 {venue.token_count}  池龄 {age}  例子 {samples}"
        )
        for reason in venue.reasons[:2]:
            lines.append(f"    {reason}")

    focus = [t for t in tokens if t.score.priority == "focus"]
    watch = [t for t in tokens if t.score.priority == "watch"]
    lines += ["", "== 该重点关注 =="]
    if not focus:
        lines.append("没有超过 72 分的。下面是次一档。")
    for item in (focus or watch[:8]):
        token = item.token
        score = item.score
        lines.append(
            f"- {token.symbol} ({token.name})  {score.total}分  "
            f"{token.chain}/{token.dex}  市值 {_money(token.size_usd)}  "
            f"池子 {_money(token.liquidity_usd)}  24h {_money(token.volume_h24)}  "
            f"年龄 {_age(token.age_days)}"
        )
        lines.append(f"    {' | '.join(score.tags) or '无标签'}")
        for reason in score.reasons[:3]:
            lines.append(f"    + {reason}")
        for warn in score.warnings[:2]:
            lines.append(f"    ! {warn}")
        if token.url:
            lines.append(f"    {token.url}")

    if focus:
        lines += ["", "== 值得跟踪 =="]
        if not watch:
            lines.append("没有 55–71 分的。")
        for item in watch[:12]:
            token = item.token
            lines.append(
                f"- {token.symbol}  {item.score.total}分  {token.chain}/{token.dex}  "
                f"{_money(token.size_usd)}  {' | '.join(item.score.tags)}"
            )

    lines += [
        "",
        "== 已知新场子（配置） ==",
    ]
    for chain, desc in NEW_CHAINS.items():
        lines.append(f"- {chain}: {desc}")
    return "\n".join(lines) + "\n"


def render_scanning_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta http-equiv="refresh" content="2"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Fifty-X Radar 扫描中</title>
  <style>
    body {
      margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
      font-family:"Iowan Old Style","Palatino Linotype",Georgia,serif;
      background:#0c0d10; color:#f4f1ea;
    }
    main { text-align:center; padding:24px; }
    .kicker { color:#e8c07a; letter-spacing:.12em; font-size:12px; text-transform:uppercase; }
    h1 { margin:12px 0 8px; font-weight:600; }
    p { color:#9aa0a6; }
  </style>
</head>
<body>
<main>
  <p class="kicker">Fifty-X Radar</p>
  <h1>正在扫描新场子和新盘</h1>
  <p>在拉 GeckoTerminal / DexScreener，完成后这一页会自动变成结果。</p>
</main>
<script>setTimeout(function(){location.reload();}, 2000);</script>
</body>
</html>
"""


def render_html(venues: list[VenuePulse], tokens: list[ScoredToken], generated_at: datetime) -> str:
    hot = [v for v in venues if v.label != "普通场"][:10]
    focus = [t for t in tokens if t.score.priority == "focus"]
    watch = [t for t in tokens if t.score.priority == "watch"]

    def venue_card(v: VenuePulse) -> str:
        reasons = "".join(f"<li>{_esc(r)}</li>" for r in v.reasons)
        samples = ", ".join(_esc(s) for s in v.sample_symbols) or "—"
        return f"""
        <article class="card">
          <div class="kicker">{_esc(v.label)}</div>
          <h3>{_esc(v.chain)} / {_esc(v.dex)}</h3>
          <p class="meta">24h 成交 {_esc(_money(v.volume_h24))} · {v.token_count} 个样本 · 池龄 {_esc(_age(v.median_age_days))}</p>
          <p class="samples">例子：{samples}</p>
          <ul>{reasons}</ul>
        </article>"""

    def token_card(item: ScoredToken, kind: str) -> str:
        token, score = item.token, item.score
        reasons = "".join(f"<li>{_esc(r)}</li>" for r in score.reasons[:5])
        warnings = "".join(f"<li class='warn'>{_esc(w)}</li>" for w in score.warnings[:3])
        tags = "".join(f"<span class='tag'>{_esc(t)}</span>" for t in score.tags)
        link = f"<a href='{_esc(token.url)}' target='_blank' rel='noreferrer'>打开行情</a>" if token.url else ""
        return f"""
        <article class="card token {kind}">
          <div class="score">{score.total}</div>
          <div>
            <div class="kicker">{_esc(token.chain)} / {_esc(token.dex)}</div>
            <h3>{_esc(token.symbol)} <small>{_esc(token.name)}</small></h3>
            <p class="meta">
              市值 {_esc(_money(token.size_usd))} · 池子 {_esc(_money(token.liquidity_usd))} ·
              24h {_esc(_money(token.volume_h24))} · {_esc(_pct(token.price_change_h24))} ·
              {_esc(_age(token.age_days))}
            </p>
            <div class="tags">{tags}</div>
            <div class="bars">
              <span>场子 {score.venue}</span>
              <span>叙事 {score.narrative}</span>
              <span>结构 {score.structure}</span>
              <span>支柱 {score.pillar}</span>
            </div>
            <ul>{reasons}{warnings}</ul>
            {link}
          </div>
        </article>"""

    venue_html = "".join(venue_card(v) for v in hot) or "<p class='empty'>这一轮没有扫到足够热的新链/发射台。</p>"
    focus_html = "".join(token_card(t, "focus") for t in focus) or "<p class='empty'>没有 72 分以上的币。不是每天都有开盘段人选。</p>"
    watch_html = "".join(token_card(t, "watch") for t in watch[:16]) or "<p class='empty'>没有次一档人选。</p>"
    known = "".join(f"<li><strong>{_esc(k)}</strong> — {_esc(v)}</li>" for k, v in NEW_CHAINS.items())

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>Fifty-X Radar</title>
  <style>
    :root {{
      --bg:#0c0d10; --card:#16181d; --ink:#f4f1ea; --muted:#9aa0a6;
      --line:#2a2e36; --accent:#e8c07a; --good:#8fd19e; --bad:#ef9a9a;
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0; font-family:"Iowan Old Style", "Palatino Linotype", Georgia, serif;
      background:radial-gradient(1200px 500px at 10% -10%, #242018 0%, var(--bg) 45%);
      color:var(--ink); padding:32px 20px 80px;
    }}
    main {{ max-width:1080px; margin:0 auto; }}
    h1 {{ font-weight:600; letter-spacing:-.02em; margin:0 0 8px; }}
    h2 {{ margin:36px 0 12px; font-size:22px; }}
    .lede, .meta, .samples, small {{ color:var(--muted); }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:14px; }}
    .card {{
      background:var(--card); border:1px solid var(--line); border-radius:16px;
      padding:16px 16px 12px; position:relative;
    }}
    .card.token {{ display:flex; gap:14px; grid-column:1 / -1; }}
    .score {{
      width:64px; height:64px; border-radius:18px; display:flex; align-items:center;
      justify-content:center; font-size:24px; background:#201c16; color:var(--accent);
      flex:0 0 auto;
    }}
    .kicker {{ font-size:12px; color:var(--accent); text-transform:uppercase; letter-spacing:.08em; }}
    h3 {{ margin:6px 0; font-size:20px; }}
    ul {{ margin:8px 0 0; padding-left:18px; color:#d9d6cf; }}
    .warn {{ color:var(--bad); }}
    .tag {{
      display:inline-block; margin:4px 6px 0 0; padding:2px 8px; border-radius:999px;
      border:1px solid var(--line); font-size:12px; color:var(--muted);
    }}
    .bars span {{
      display:inline-block; margin-right:10px; font-size:12px; color:var(--good);
    }}
    a {{ color:var(--accent); }}
    .empty {{ color:var(--muted); }}
    footer {{ margin-top:40px; color:var(--muted); font-size:13px; }}
  </style>
</head>
<body>
<main>
  <p class="kicker">Fifty-X Radar</p>
  <h1>该盯哪些新场子和新叙事</h1>
  <p class="lede">
    扫描时间 {_esc(generated_at.strftime("%Y-%m-%d %H:%M UTC"))}。
    规则来自近几个月能核验的 50 倍样本：新场子、独占叙事、浅开盘；能多活几天的还要有第二支柱。
    这不是投资建议。
  </p>

  <h2>新场子</h2>
  <div class="grid">{venue_html}</div>

  <h2>重点关注</h2>
  <div class="grid">{focus_html}</div>

  <h2>值得跟踪</h2>
  <div class="grid">{watch_html}</div>

  <h2>配置里的新场子</h2>
  <ul>{known}</ul>

  <footer>
    数据来自 GeckoTerminal 与 DexScreener 公开接口。仿盘、无量盘和已过大的龙头会被降权或标警告。
    50 倍发生在出生，不发生在市值过亿之后。
  </footer>
</main>
</body>
</html>
"""


def render_json(venues: list[VenuePulse], tokens: Iterable[ScoredToken], generated_at: datetime) -> str:
    payload = {
        "generated_at": generated_at.astimezone(timezone.utc).isoformat(),
        "disclaimer": "Not investment advice. 50x happened at launch, not after large caps.",
        "venues": [
            {
                "chain": v.chain,
                "dex": v.dex,
                "label": v.label,
                "token_count": v.token_count,
                "volume_h24": v.volume_h24,
                "median_age_days": v.median_age_days,
                "reasons": v.reasons,
                "sample_symbols": v.sample_symbols,
            }
            for v in venues
        ],
        "tokens": [
            {
                "symbol": t.token.symbol,
                "name": t.token.name,
                "chain": t.token.chain,
                "dex": t.token.dex,
                "score": t.score.total,
                "priority": t.score.priority,
                "parts": {
                    "venue": t.score.venue,
                    "narrative": t.score.narrative,
                    "structure": t.score.structure,
                    "pillar": t.score.pillar,
                },
                "mcap": t.token.size_usd,
                "liquidity": t.token.liquidity_usd,
                "volume_h24": t.token.volume_h24,
                "age_days": t.token.age_days,
                "url": t.token.url,
                "tags": t.score.tags,
                "reasons": t.score.reasons,
                "warnings": t.score.warnings,
            }
            for t in tokens
            if t.score.watch
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
