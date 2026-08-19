from __future__ import annotations

from .canvas import Drawing, new_sheet, wrap_cn
from .model import BuildingModel
from .plan import draw_architecture_plan, draw_columns, draw_grid


def architecture_sheets(m: BuildingModel, num) -> list[Drawing]:
    sheets: list[Drawing] = []
    sheets.append(_notes(m, num("建施")))
    sheets.append(_site(m, num("建施")))
    floors_to_draw = []
    if m.spec.basement:
        floors_to_draw.append(-1)
    floors_to_draw.append(1)
    if m.spec.floors >= 3:
        floors_to_draw.append(m.typical_floor())
    if m.spec.floors >= 2 and m.spec.floors not in floors_to_draw:
        floors_to_draw.append(m.spec.floors)
    seen = set()
    for fl in floors_to_draw:
        if fl in seen or fl not in m.plans:
            continue
        seen.add(fl)
        d = new_sheet(num("建施"), f"{m.floor_name(fl)}平面图", "建筑", m)
        draw_architecture_plan(d, m, m.plans[fl])
        sheets.append(d)
    sheets.append(_roof(m, num("建施")))
    sheets.append(_elevation(m, num("建施"), "south"))
    sheets.append(_elevation(m, num("建施"), "east"))
    sheets.append(_section(m, num("建施")))
    sheets.append(_stair(m, num("建施")))
    sheets.append(_openings_table(m, num("建施")))
    return sheets


def _notes(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "建筑设计说明", "建筑", m)
    d.scale = 1
    y = 28
    d.paper_text(210, y, "建 筑 设 计 说 明", 6.5)
    y = 40
    for i, line in enumerate(m.notes.get("建筑", [])):
        for w in wrap_cn(f"{i+1}. {line}", 42):
            d.paper_text(40, y, w, 3.2, "s")
            y += 7
        y += 2
    sm = m.summary()
    rows = [
        ("工程名称", sm["name"]),
        ("建筑性质", sm["building_type"]),
        ("建设地点", sm["location"]),
        ("层数", f"地上{sm['floors']}层" + (f" / 地下{sm['basement']}层" if sm["basement"] else "")),
        ("建筑高度", f"{sm['height']} m"),
        ("单层面积", f"{sm['floor_area']} ㎡"),
        ("总建筑面积", f"{sm['total_area']} ㎡"),
        ("平面尺寸", f"{sm['length']} × {sm['width']} m"),
        ("柱网", f"{sm['span_x']} × {sm['span_y']} m"),
        ("层高", f"{sm['floor_height']} m"),
        ("结构", sm["structure"]),
        ("耐火等级", sm["fire_rating"]),
        ("抗震", sm["seismic"]),
        ("楼梯/电梯", f"{sm['n_stairs']} / {sm['n_elevators']}"),
    ]
    y += 4
    d.paper_text(40, y, "主要技术指标", 4.0, "s")
    y += 8
    d.paper_rect(38, y - 4, 340, 8 + 6.2 * len(rows), lw=0.25)
    for k, v in rows:
        d.paper_text(50, y, k, 2.8, "s")
        d.paper_text(140, y, str(v), 2.8, "s")
        y += 6.2
    y += 8
    d.paper_text(40, y, "图例：本图为自动生成示意，墙厚、门窗、核心筒位置可在深化阶段调整。", 2.6, "s")
    return d


def _site(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "总平面图", "建筑", m)
    L, W = m.length, m.width
    site_l, site_w = L + 24, W + 20
    d.fit_plan(-8, -8, site_l + 4, site_w + 4)
    # plot
    d.rect(0, 0, site_l, site_w, "S-SITE", 0.35)
    d.pline([(1, 1), (site_l - 1, 1), (site_l - 1, site_w - 1), (1, site_w - 1)], "S-SITE", 0.2, True, fill="#e8f5e9")
    bx, by = 12, 8
    d.rect(bx, by, L, W, "S-WALL", 0.45, fill="#c5d4e8")
    d.text(bx + L / 2, by + W / 2, f"{m.spec.building_type}\n{m.spec.floors}F", "S-TEXT", 3.2)
    # road
    d.rect(-4, -6, site_l + 8, 5.2, "S-HATCH", 0.1, fill="#9ca3af")
    d.text(site_l / 2, -3.4, "规划道路", "S-TEXT", 2.5)
    # fire lane
    d.pline([(bx - 4, by - 4), (bx + L + 4, by - 4), (bx + L + 4, by + W + 4), (bx - 4, by + W + 4)], "S-FIRE", 0.3, True)
    d.text(bx + L / 2, by - 5.2, "消防车道 4.0m", "S-FIRE", 2.2)
    # parking
    for i in range(8):
        d.rect(2 + i * 2.6, site_w - 6.5, 2.4, 5.2, "S-SITE", 0.15)
    d.text(12, site_w - 7.4, "地面停车（示意）", "S-TEXT", 2.2)
    # entrance
    d.pline([(bx + L / 2 - 2, by), (bx + L / 2, by - 3), (bx + L / 2 + 2, by)], "S-DOOR", 0.3)
    d.text(bx + L / 2, by - 3.8, "主入口", "S-TEXT", 2.2)
    d.dim_h(0, site_l, -7.5)
    d.dim_v(0, site_w, -6.5)
    from .canvas import north_arrow, scale_bar
    north_arrow(d, 52, 42)
    scale_bar(d, 48, 64)
    d.legend = [("建设用地", "绿底"), ("主体建筑", "蓝底"), ("消防车道", "红线")]
    return d


def _roof(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "屋顶平面图", "建筑", m)
    d.fit_plan(-5, -5, m.length + 5, m.width + 5)
    draw_grid(d, m, with_dim=True)
    d.rect(0, 0, m.length, m.width, "S-WALL", 0.4, fill="#e2e8f0")
    d.rect(0.4, 0.4, m.length - 0.8, m.width - 0.8, "S-WALL", 0.2)
    # parapet dim
    d.text(m.length / 2, m.width / 2, "上人屋面 / 防水层 示意", "S-TEXT", 3.0)
    d.rect(m.length * 0.4, m.width * 0.35, 6.0, 4.5, "S-FURN", 0.25, fill="#fecaca")
    d.text(m.length * 0.4 + 3, m.width * 0.35 + 2.2, "电梯机房", "S-TEXT", 2.2)
    d.rect(m.length * 0.55, m.width * 0.35, 4.0, 3.5, "S-PLUMB-W", 0.25, fill="#bae6fd")
    d.text(m.length * 0.55 + 2, m.width * 0.35 + 1.7, "水箱间", "S-TEXT", 2.2)
    d.rect(m.length - 8, m.width - 6, 6, 4, "S-HVAC", 0.25, fill="#a5f3fc")
    d.text(m.length - 5, m.width - 4, "冷却塔/风机", "S-TEXT", 2.0)
    # drains
    for x in (4, m.length / 2, m.length - 4):
        for y in (3, m.width - 3):
            d.circle(x, y, 0.25, "S-PLUMB-D", 0.2)
            d.text(x, y - 0.7, "雨水口", "S-PLUMB-D", 1.6)
    draw_columns(d, m)
    from .canvas import north_arrow, scale_bar
    north_arrow(d, 50, 40)
    scale_bar(d, 48, 62)
    return d


def _elevation(m: BuildingModel, number: str, face: str) -> Drawing:
    title = "南立面图" if face == "south" else "东立面图"
    d = new_sheet(number, title, "建筑", m)
    span = m.length if face == "south" else m.width
    H = m.height
    d.fit_plan(-4, -3, span + 4, H + 4, box=(32, 14, 408, 238))
    # ground
    d.line(-3, 0, span + 3, 0, "S-SITE", 0.45)
    d.text(-2.2, -1.0, "±0.000", "S-DIM", 2.2)
    d.rect(0, 0, span, H, "S-WALL", 0.35, fill="#e8eef6")
    fh = m.spec.floor_height
    p = __import__("shigongtu.engine.model", fromlist=["PRESETS"]).PRESETS[m.spec.building_type]
    ww, wh, sill = p["window_w"], p["window_h"], p["sill"]
    for i in range(m.spec.floors):
        y = i * fh
        d.line(0, y, span, y, "S-WALL", 0.15)
        d.text(-2.4, y + fh, f"{y + fh:.3f}", "S-DIM", 1.8)
        x = 1.2
        while x + ww < span - 0.8:
            d.rect(x, y + sill, ww, wh, "S-WIND", 0.2, fill="#dbeafe")
            x += ww + 1.5
    # roof
    d.line(-0.3, H, span + 0.3, H, "S-WALL", 0.4)
    d.rect(-0.15, H, span + 0.3, 1.2, "S-WALL", 0.25, fill="#94a3b8")
    d.text(span / 2, H + 2.2, f"女儿墙 建筑高度 {H:.1f}m", "S-TEXT", 2.5)
    d.dim_v(0, H, span + 1.5, 0.8)
    d.dim_h(0, span, -2.2)
    # entrance
    if face == "south":
        d.rect(span / 2 - 1.5, 0, 3.0, 3.0, "S-DOOR", 0.25, fill="#fef3c7")
    from .canvas import scale_bar
    scale_bar(d, 48, 62)
    return d


def _section(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "1-1 剖面图", "建筑", m)
    span = min(m.width, 24)
    H = m.height
    d.fit_plan(-5, -4, span + 6, H + 5)
    d.line(-3, 0, span + 4, 0, "S-SITE", 0.4)
    fh = m.spec.floor_height
    for i in range(m.spec.floors + 1):
        y = i * fh
        d.rect(-0.15, y - m.slab, span + 0.15, m.slab, "S-STRUCT", 0.2, fill="#64748b")
        if i < m.spec.floors:
            d.text(span + 1.4, y + fh / 2, f"层高 {fh}m", "S-DIM", 2.0)
    # basement
    if m.spec.basement:
        d.rect(-0.15, -3.6, span + 0.15, 0.3, "S-STRUCT", 0.2, fill="#475569")
        d.text(span / 2, -2.0, "地下室（示意）", "S-TEXT", 2.2)
        d.rect(-0.8, -3.6, 0.8, 3.6, "S-STRUCT", 0.2, fill="#334155")
    # walls
    d.rect(-0.2, 0, 0.2, H, "S-WALL", 0.15, fill="#222")
    d.rect(span, 0, 0.2, H, "S-WALL", 0.15, fill="#222")
    # stair schematic
    for i in range(m.spec.floors):
        y0 = i * fh
        n = 10
        for k in range(n):
            d.line(2 + k * 0.28, y0 + k * fh / n, 2 + (k + 1) * 0.28, y0 + k * fh / n, "S-WALL", 0.15)
        d.line(2, y0, 2 + 2.8, y0 + fh, "S-WALL", 0.15)
    d.rect(1.8, 0, 0.25, H, "S-WALL", 0.15, fill="#444")
    d.text(3.6, H / 2, "楼梯", "S-TEXT", 2.2)
    d.dim_v(0, H, -2.5, -0.3)
    d.text(span / 2, H + 2.5, "剖面位置见首层平面 1-1", "S-TEXT", 2.5)
    return d


def _stair(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "楼梯详图（示意）", "建筑", m)
    d.fit_plan(-2, -2, 12, 10)
    d.rect(0, 0, 2.7, 6.6, "S-WALL", 0.3, fill="#fde68a")
    d.rect(0, 0, 2.7, 6.6, "S-WALL", 0.35)
    # runs
    for i in range(12):
        d.line(0.15, 0.2 + i * 0.26, 1.25, 0.2 + i * 0.26, "S-WALL", 0.15)
    d.rect(0.15, 3.3, 2.4, 1.2, "S-HATCH", 0.15, fill="#e5e7eb")
    d.text(1.35, 3.9, "休息平台", "S-TEXT", 2.0)
    for i in range(12):
        d.line(1.45, 4.6 + i * 0.16, 2.55, 4.6 + i * 0.16, "S-WALL", 0.15)
    d.text(1.35, 7.2, "上行", "S-TEXT", 2.2)
    d.dim_h(0, 2.7, -0.8)
    d.dim_v(0, 6.6, -1.0)
    d.paper_text(48, 80, "踏步 260×150 示意，实际按层高均分。楼梯净宽、疏散宽度须按防火规范核算。", 2.6, "s")
    return d


def _openings_table(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "门窗表", "建筑", m)
    d.scale = 1
    d.paper_text(210, 28, "门 窗 表（示意统计）", 5.5)
    headers = ["编号", "名称", "洞口宽×高(mm)", "数量(估算)", "所在位置", "备注"]
    doors = [
        ("M1", "玻璃门", "2400×3000", max(1, m.spec.floors // 6 + 1), "主入口", "首层"),
        ("M2", "防火门", "1500×2100", m.n_stairs * m.spec.floors, "楼梯间", "甲/乙级按层数"),
        ("M3", "电梯门", "1100×2100", max(1, m.n_elevators) * m.spec.floors, "电梯", ""),
        ("M4", "房间门", "900×2100", max(8, int(m.actual_floor_area / 25)) * m.spec.floors, "房间", ""),
        ("M5", "卫生间门", "800×2100", 4 * m.spec.floors, "卫生间", "防潮"),
    ]
    p = __import__("shigongtu.engine.model", fromlist=["PRESETS"]).PRESETS[m.spec.building_type]
    ww, wh = int(p["window_w"] * 1000), int(p["window_h"] * 1000)
    n_win = max(12, int((m.length + m.width) * 2 / (p["window_w"] + 1.5))) * m.spec.floors
    windows = [
        ("C1", "外窗", f"{ww}×{wh}", n_win, "外墙", "节能计算确定玻璃"),
        ("C2", "卫生间窗", "600×900", 2 * m.spec.floors, "卫生间", "铝百叶可改"),
    ]
    y = 42
    x0 = 36
    widths = [28, 40, 55, 40, 50, 80]
    def row(vals, header=False):
        nonlocal y
        x = x0
        for w, v in zip(widths, vals):
            d.paper_rect(x, y, w, 8, lw=0.2, fill="#e8eef6" if header else "none")
            d.paper_text(x + w / 2, y + 4, str(v), 2.4)
            x += w
        y += 8
    row(headers, True)
    for r in doors + windows:
        row(r)
    y += 10
    d.paper_text(40, y, "数量按规则估算，深化时以各层平面实际统计为准。", 2.6, "s")
    return d
