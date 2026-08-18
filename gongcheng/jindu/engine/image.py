from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from jindu.engine.schedule import enrich_project, inclusive_days, parse_date


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = []
    windir = Path("C:/Windows/Fonts")
    if windir.exists():
        names.extend(
            [
                windir / ("msyhbd.ttc" if bold else "msyh.ttc"),
                windir / "msyh.ttf",
                windir / "simhei.ttf",
                windir / "simsun.ttc",
            ]
        )
    names.extend(
        [
            Path("/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
            Path("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"),
        ]
    )
    for path in names:
        if path.exists():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def export_png(project: dict[str, Any], today: date | None = None) -> bytes:
    today = today or date.today()
    data = enrich_project(project, today)
    tasks = data.get("tasks") or []
    if not tasks:
        tasks = [{"wbs": "-", "name": "暂无任务", "planned_start": data.get("contract_start"), "planned_end": data.get("contract_end"), "progress": 0, "status": "未开始"}]
    dates = []
    for task in tasks:
        for key in ("planned_start", "planned_end"):
            d = parse_date(task.get(key))
            if d:
                dates.append(d)
    if not dates:
        dates = [today, today + timedelta(days=30)]
    g0 = min(dates)
    g1 = max(dates)
    span = max(inclusive_days(g0, g1), 1)
    left_w = 280
    top_h = 92
    row_h = 26
    day_w = 12 if span <= 120 else 6 if span <= 240 else 3
    width = left_w + span * day_w + 40
    height = top_h + row_h * len(tasks) + 48
    img = Image.new("RGB", (width, height), "#F8FAFC")
    draw = ImageDraw.Draw(img)
    title_font = _font(20, True)
    small = _font(12)
    tiny = _font(10)
    draw.rectangle((0, 0, width, 56), fill="#12365F")
    title = f"{data.get('name') or '工程'} 施工进度横道图"
    draw.text((16, 10), title, font=title_font, fill="#FFFFFF")
    stats = data.get("stats") or {}
    sub = f"总进度 {stats.get('overall', 0)}%   滞后 {stats.get('delayed_count', 0)} 项   {stats.get('range_start') or ''} ～ {stats.get('range_end') or ''}   导出 {stats.get('today')}"
    draw.text((16, 34), sub, font=small, fill="#DBE7F6")

    # month bands
    cur = g0
    while cur <= g1:
        if cur.month == 12:
            month_end = date(cur.year + 1, 1, 1) - timedelta(days=1)
        else:
            month_end = date(cur.year, cur.month + 1, 1) - timedelta(days=1)
        stop = min(month_end, g1)
        x0 = left_w + (cur - g0).days * day_w
        x1 = left_w + (stop - g0).days * day_w + day_w
        draw.rectangle((x0, 56, x1, top_h), fill="#E8F0F8", outline="#D7E0EA")
        draw.text((x0 + 4, 62), f"{cur.year}-{cur.month:02d}", font=tiny, fill="#1B4F8A")
        cur = stop + timedelta(days=1)

    colors = {
        "已完成": "#15803D",
        "延期完成": "#15803D",
        "进行中": "#1D4ED8",
        "滞后": "#EA580C",
        "未开始": "#93C5FD",
    }
    for i, task in enumerate(tasks):
        y = top_h + i * row_h
        bg = "#FFFFFF" if i % 2 == 0 else "#F1F5F9"
        if task.get("critical") and not task.get("summary"):
            bg = "#FEE2E2"
        draw.rectangle((0, y, width, y + row_h), fill=bg)
        draw.line((0, y + row_h, width, y + row_h), fill="#E2E8F0")
        label = f"{task.get('wbs') or ''}  {task.get('name') or ''}"
        draw.text((8, y + 6), label[:22], font=small, fill="#1C2A3A")
        start = parse_date(task.get("planned_start"))
        end = parse_date(task.get("planned_end"))
        if not start or not end:
            continue
        x0 = left_w + (start - g0).days * day_w
        x1 = left_w + (end - g0).days * day_w + day_w
        y0, y1 = y + 6, y + row_h - 6
        status = str(task.get("status") or "未开始")
        draw.rounded_rectangle((x0, y0, x1, y1), radius=3, fill=colors.get(status, "#93C5FD"))
        progress = int(task.get("progress") or 0)
        if 0 < progress < 100:
            px = x0 + int((x1 - x0) * progress / 100)
            draw.rounded_rectangle((x0, y0, max(x0 + 2, px), y1), radius=3, fill="#1E3A8A")

    tx = left_w + (today - g0).days * day_w
    if left_w <= tx <= width:
        draw.line((tx, 56, tx, height - 24), fill="#DC2626", width=2)
        draw.text((tx + 4, height - 20), "今日", font=tiny, fill="#DC2626")
    draw.text((16, height - 20), "蓝=进行中　绿=完成　橙=滞后　红线=今日　浅红行=关键线路", font=tiny, fill="#5E7186")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
