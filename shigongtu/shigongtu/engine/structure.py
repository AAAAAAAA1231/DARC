from __future__ import annotations

from .canvas import Drawing, new_sheet, wrap_cn
from .model import BuildingModel
from .plan import draw_columns, draw_grid, setup_plan


def structure_sheets(m: BuildingModel, num) -> list[Drawing]:
    return [
        _notes(m, num("结施")),
        _foundation(m, num("结施")),
        _column_plan(m, num("结施")),
        _slab_plan(m, num("结施")),
        _frame_section(m, num("结施")),
    ]


def _notes(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "结构设计说明", "结构", m)
    d.scale = 1
    y = 28
    d.paper_text(210, y, "结 构 设 计 说 明", 6.5)
    y = 42
    sm = m.summary()
    for i, line in enumerate(m.notes.get("结构", [])):
        for w in wrap_cn(f"{i+1}. {line}", 42):
            d.paper_text(40, y, w, 3.2, "s")
            y += 7
        y += 2
    y += 4
    rows = [
        ("结构体系", sm["structure"]),
        ("抗震设防", sm["seismic"]),
        ("基础形式", sm["foundation"]),
        ("柱截面(示意)", f"{sm['col_size_mm']}×{sm['col_size_mm']}"),
        ("主梁(示意)", sm["beam"]),
        ("板厚(示意)", f"{sm['slab_mm']} mm"),
        ("混凝土(示意)", "柱 C35，梁板 C30" if m.spec.floors >= 6 else "柱 C30，梁板 C30"),
        ("钢筋(示意)", "HRB400 / HPB300"),
        ("保护层(示意)", "梁柱 20mm，板 15mm，基础 40mm"),
    ]
    d.paper_text(40, y, "构件估算一览（非计算结果）", 3.6, "s")
    y += 8
    for k, v in rows:
        d.paper_text(50, y, k, 2.8, "s")
        d.paper_text(160, y, v, 2.8, "s")
        y += 6.5
    return d


def _foundation(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "基础平面布置图", "结构", m)
    setup_plan(d, m)
    draw_grid(d, m)
    fs = m.col_size * (3.2 if "筏板" in m.spec.foundation else 2.4)
    if "筏板" in m.spec.foundation:
        d.rect(-0.8, -0.8, m.length + 1.6, m.width + 1.6, "S-STRUCT", 0.4, fill="#cbd5e1")
        d.text(m.length / 2, m.width / 2, f"筏板基础 厚 400~600mm 示意\n{m.spec.foundation}", "S-TEXT", 3.0)
        draw_columns(d, m)
    else:
        for c in m.columns:
            d.rect(c.x - fs / 2, c.y - fs / 2, fs, fs, "S-STRUCT", 0.25, fill="#94a3b8")
            d.rect(c.x - m.col_size / 2, c.y - m.col_size / 2, m.col_size, m.col_size, "S-COL", 0.3, fill="#1e3a5f")
        d.text(m.length / 2, m.width + 3.2, f"{m.spec.foundation}  独立基础平面尺寸约 {int(fs*1000)}×{int(fs*1000)}（示意）", "S-TEXT", 2.6)
    # strip for 砖混
    if m.spec.foundation == "条形基础":
        for y in m.axes_y:
            d.rect(-0.4, y - 0.5, m.length + 0.8, 1.0, "S-STRUCT", 0.2, fill="#94a3b8")
    return d


def _column_plan(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "柱网及剪力墙平面图", "结构", m)
    setup_plan(d, m)
    draw_grid(d, m)
    draw_columns(d, m)
    if m.spec.structure in ("框剪", "剪力墙"):
        # shear walls around core-ish center and ends
        d.rect(m.length / 2 - 0.2, 2.0, 0.2, min(8.0, m.width - 4), "S-STRUCT", 0.2, fill="#7f1d1d")
        d.rect(2.0, m.width / 2 - 0.2, min(8.0, m.length - 4), 0.2, "S-STRUCT", 0.2, fill="#7f1d1d")
        d.text(m.length / 2 + 1.2, 6.0, "剪力墙 200/300 示意", "S-FIRE", 2.2)
    for c in m.columns:
        if c.i in (0, m.nx) and c.j in (0, m.ny):
            d.text(c.x, c.y + m.col_size / 2 + 0.5, f"KZ {int(m.col_size*1000)}", "S-STRUCT", 1.6)
    d.text(m.length / 2, m.width + 3.4, f"柱 {m.nx+1}×{m.ny+1} 根  截面 {int(m.col_size*1000)}×{int(m.col_size*1000)}", "S-TEXT", 2.8)
    return d


def _slab_plan(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, f"{m.floor_name(m.typical_floor())}梁板结构平面图", "结构", m)
    setup_plan(d, m)
    draw_grid(d, m)
    # beams on grid
    bw, bh = m.beam_b, m.beam_h
    for x in m.axes_x:
        d.rect(x - bw / 2, 0, bw, m.width, "S-STRUCT", 0.15, fill="#93c5fd")
    for y in m.axes_y:
        d.rect(0, y - bw / 2, m.length, bw, "S-STRUCT", 0.15, fill="#60a5fa")
    draw_columns(d, m)
    # slab annotation each bay
    for i in range(m.nx):
        for j in range(m.ny):
            cx = (m.axes_x[i] + m.axes_x[i + 1]) / 2
            cy = (m.axes_y[j] + m.axes_y[j + 1]) / 2
            d.text(cx, cy, f"h={int(m.slab*1000)}", "S-TEXT", 1.8)
    d.text(m.length / 2, m.width + 3.3, f"主梁 {int(bw*1000)}×{int(bh*1000)}  次梁/板带示意  板厚 {int(m.slab*1000)}mm", "S-TEXT", 2.6)
    return d


def _frame_section(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "框架剖面示意图", "结构", m)
    nshow = min(m.nx, 5)
    span = m.spec.span_x
    H = m.height
    d.fit_plan(-3, -4, nshow * span + 4, H + 4)
    d.line(-2, 0, nshow * span + 2, 0, "S-SITE", 0.4)
    for i in range(nshow + 1):
        x = i * span
        d.rect(x - m.col_size / 2, 0, m.col_size, H, "S-COL", 0.25, fill="#1e3a5f")
    for i in range(m.spec.floors + 1):
        y = i * m.spec.floor_height
        d.rect(-0.2, y - m.beam_h, nshow * span + 0.2, m.beam_h, "S-STRUCT", 0.2, fill="#60a5fa")
        d.text(-1.8, y, f"{y:.2f}", "S-DIM", 1.8)
    if m.spec.basement:
        d.rect(-0.8, -3.3, nshow * span + 1.6, 0.5, "S-STRUCT", 0.25, fill="#475569")
        d.text(nshow * span / 2, -2.2, m.spec.foundation, "S-TEXT", 2.2)
    d.dim_h(0, span, -1.2)
    d.text(nshow * span / 2, H + 2.2, f"柱 {int(m.col_size*1000)}  梁 {int(m.beam_b*1000)}×{int(m.beam_h*1000)} 示意，须以计算书为准", "S-TEXT", 2.4)
    return d
