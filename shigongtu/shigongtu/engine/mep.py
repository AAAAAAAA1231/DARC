from __future__ import annotations

from .canvas import Drawing, new_sheet, wrap_cn
from .model import BuildingModel
from .plan import (
    corridor_polyline,
    draw_architecture_plan,
    grid_points,
    place_along,
    rooms_of,
    setup_plan,
)


def _base_plan(m: BuildingModel, number: str, name: str, disc: str, fl: int | None = None) -> Drawing:
    d = new_sheet(number, name, disc, m)
    fl = m.typical_floor() if fl is None else fl
    draw_architecture_plan(d, m, m.plans[fl])
    return d


def water_sheets(m: BuildingModel, num) -> list[Drawing]:
    sheets = [_text_sheet(m, num("水施"), "给排水设计说明", "给排水", m.notes.get("给排水", []))]
    sheets.append(_water_plan(m, num("水施"), "给"))
    sheets.append(_water_plan(m, num("水施"), "排"))
    sheets.append(_water_riser(m, num("水施")))
    return sheets


def electrical_sheets(m: BuildingModel, num) -> list[Drawing]:
    return [
        _text_sheet(m, num("电施"), "电气设计说明", "电气", m.notes.get("电气", [])),
        _elec_plan(m, num("电施"), "照明"),
        _elec_plan(m, num("电施"), "插座"),
        _elec_riser(m, num("电施")),
        _lightning(m, num("电施")),
    ]


def heating_sheets(m: BuildingModel, num) -> list[Drawing]:
    return [
        _text_sheet(m, num("暖施"), "采暖设计说明", "暖通", m.notes.get("暖通", [])),
        _heat_plan(m, num("暖施")),
        _heat_riser(m, num("暖施")),
    ]


def ventilation_sheets(m: BuildingModel, num) -> list[Drawing]:
    return [
        _text_sheet(m, num("风施"), "通风空调设计说明", "通风", m.notes.get("通风", [])),
        _vent_plan(m, num("风施")),
        _ac_plan(m, num("风施")),
    ]


def fire_sheets(m: BuildingModel, num) -> list[Drawing]:
    return [
        _text_sheet(m, num("消施"), "消防设计说明", "消防", m.notes.get("消防", [])),
        _hydrant_plan(m, num("消施")),
        _sprinkler_plan(m, num("消施")),
        _alarm_plan(m, num("消施")),
        _smoke_plan(m, num("消施")),
    ]


def _text_sheet(m: BuildingModel, number: str, title: str, disc: str, lines: list[str]) -> Drawing:
    d = new_sheet(number, title, disc, m)
    d.scale = 1
    d.paper_text(210, 28, title, 6.0)
    y = 44
    for i, line in enumerate(lines):
        for w in wrap_cn(f"{i+1}. {line}", 42):
            d.paper_text(40, y, w, 3.2, "s")
            y += 7
        y += 2
    sm = m.summary()
    y += 6
    d.paper_text(40, y, f"工程：{sm['name']}  {sm['building_type']}  {sm['floors']}层  {sm['total_area']}㎡", 2.8, "s")
    return d


def _water_plan(m: BuildingModel, number: str, kind: str) -> Drawing:
    title = "给水平面图" if kind == "给" else "污废水平面图"
    layer = "S-PLUMB-W" if kind == "给" else "S-PLUMB-D"
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}{title}", "给排水")
    path = corridor_polyline(m, m.typical_floor())
    d.pline(path, layer, 0.35)
    baths = rooms_of(m, m.typical_floor(), {"卫生间", "厨房"})
    for r in baths:
        d.line(r.cx, r.cy, path[0][0] if kind == "给" else path[-1][0], path[0][1], layer, 0.22)
        if kind == "给":
            d.circle(r.x + 0.6, r.y + 0.6, 0.18, layer, 0.2, fill="#7dd3fc")
            d.circle(r.x + 1.3, r.y + 0.6, 0.12, layer, 0.2)
            d.text(r.cx, r.y + 1.1, "洗手盆/蹲便示意", layer, 1.5)
        else:
            d.circle(r.x + r.w - 0.7, r.y + 0.5, 0.16, layer, 0.2)
            d.text(r.x + r.w - 0.7, r.y + 1.0, "地漏", layer, 1.5)
            d.circle(r.cx, r.cy, 0.22, layer, 0.25)
            d.text(r.cx, r.cy - 0.5, "DN100", layer, 1.6)
    shafts = rooms_of(m, m.typical_floor(), {"竖井"})
    for s in shafts:
        d.rect(s.x, s.y, s.w, s.h, layer, 0.3)
        d.text(s.cx, s.cy, "水管井", layer, 1.8)
    return d


def _water_riser(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "给排水系统图", "给排水", m)
    d.scale = 1
    d.paper_text(210, 26, "给排水系统示意图", 5.0)
    xg, xd = 90, 250
    d.paper_text(xg, 40, "生活给水", 3.2)
    d.paper_text(xd, 40, "污废水", 3.2)
    y0 = 220
    d.paper_line(xg, 50, xg, y0, "S-PLUMB-W", 0.7)
    d.paper_line(xd, 50, xd, y0, "S-PLUMB-D", 0.7)
    for i in range(m.spec.floors):
        y = y0 - 12 - i * min(18, 160 / max(m.spec.floors, 1))
        d.paper_line(xg, y, xg + 40, y, "S-PLUMB-W", 0.4)
        d.paper_text(xg + 48, y, f"{i+1}F 用水点", 2.4, "s", "S-PLUMB-W")
        d.paper_line(xd - 40, y, xd, y, "S-PLUMB-D", 0.4)
        d.paper_text(xd - 88, y, f"{i+1}F 卫生器具", 2.4, "s", "S-PLUMB-D")
    d.paper_text(xg, 232, "市政给水 / 水箱", 2.6, "m", "S-PLUMB-W")
    d.paper_text(xd, 232, "出户 → 化粪池/市政", 2.6, "m", "S-PLUMB-D")
    return d


def _elec_plan(m: BuildingModel, number: str, kind: str) -> Drawing:
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}{kind}平面图", "电气")
    if kind == "照明":
        pts = grid_points(m, step=3.6, inset=2.0)
        for x, y in pts:
            d.circle(x, y, 0.22, "S-ELEC", 0.2)
            d.line(x - 0.22, y, x + 0.22, y, "S-ELEC", 0.15)
            d.line(x, y - 0.22, x, y + 0.22, "S-ELEC", 0.15)
        for r in rooms_of(m, m.typical_floor(), {"走廊", "楼梯", "门厅"}):
            d.circle(r.cx, r.cy, 0.18, "S-FIRE", 0.2, fill="#fecaca")
            d.text(r.cx, r.cy - 0.55, "应急灯", "S-FIRE", 1.5)
    else:
        for r in m.plans[m.typical_floor()].rooms:
            if r.kind in ("竖井", "电梯"):
                continue
            d.rect(r.x + 0.25, r.y + r.h - 0.45, 0.35, 0.25, "S-ELEC", 0.2)
            d.text(r.x + 0.9, r.y + r.h - 0.35, "插座", "S-ELEC", 1.5)
    for s in rooms_of(m, m.typical_floor(), {"竖井", "设备"}):
        if "电" in s.name or s.kind == "设备":
            d.rect(s.x, s.y, s.w, s.h, "S-ELEC", 0.35)
            d.text(s.cx, s.cy, "配电", "S-ELEC", 2.0)
    return d


def _elec_riser(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "低压配电系统图", "电气", m)
    d.scale = 1
    d.paper_text(210, 26, "低压配电系统示意图", 5.0)
    d.paper_rect(180, 40, 60, 16, "S-ELEC", 0.35)
    d.paper_text(210, 48, "变压器 / 进线", 2.6)
    d.paper_line(210, 56, 210, 72, "S-ELEC", 0.4)
    d.paper_rect(170, 72, 80, 14, "S-ELEC", 0.35)
    d.paper_text(210, 79, "低压总进线柜", 2.6)
    xs = [80, 160, 240, 320]
    names = ["照明", "插座/空调", "动力", "消防负荷"]
    for x, n in zip(xs, names):
        d.paper_line(210, 86, x, 110, "S-ELEC", 0.3)
        d.paper_rect(x - 28, 110, 56, 14, "S-ELEC", 0.3)
        d.paper_text(x, 117, n, 2.4)
        for i in range(min(m.spec.floors, 8)):
            y = 130 + i * 12
            d.paper_line(x, 124 if i == 0 else y - 12, x, y, "S-ELEC", 0.2)
            d.paper_text(x + 8, y, f"{i+1}F AL", 2.0, "s", "S-ELEC")
    return d


def _lightning(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "防雷接地平面图", "电气", m)
    setup_plan(d, m)
    d.rect(0, 0, m.length, m.width, "S-ELEC", 0.35)
    d.pline([(0, 0), (m.length, 0), (m.length, m.width), (0, m.width)], "S-ELEC", 0.4, True)
    for x in (0, m.length):
        for y in (0, m.width):
            d.circle(x, y, 0.35, "S-ELEC", 0.25)
            d.text(x + (1.2 if x == 0 else -1.2), y, "接闪带/引下", "S-ELEC", 1.6)
    d.text(m.length / 2, m.width / 2, "屋面接闪带沿女儿墙\n引下线利用柱内主筋\n接地网 R≤1Ω 示意", "S-TEXT", 2.8)
    return d


def _heat_plan(m: BuildingModel, number: str) -> Drawing:
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}采暖平面图", "暖通")
    path = corridor_polyline(m, m.typical_floor())
    d.pline(path, "S-HVAC", 0.4)
    for r in m.plans[m.typical_floor()].rooms:
        if r.kind in ("竖井", "电梯", "楼梯"):
            continue
        if r.y < 0.4 or abs(r.y + r.h - m.width) < 0.4:
            n = max(1, int(r.w / 2.4))
            for i in range(n):
                x = r.x + (i + 0.5) * r.w / n
                y = r.y + 0.35 if r.y < 0.4 else r.y + r.h - 0.35
                d.rect(x - 0.45, y - 0.12, 0.9, 0.24, "S-HVAC", 0.2, fill="#a5f3fc")
                d.text(x, y + 0.4, "散热器", "S-HVAC", 1.4)
    d.text(m.length / 2, -4.6, f"气候区 {m.spec.climate}  热水供回水 DN 示意", "S-HVAC", 2.4)
    return d


def _heat_riser(m: BuildingModel, number: str) -> Drawing:
    d = new_sheet(number, "采暖系统图", "暖通", m)
    d.scale = 1
    d.paper_text(210, 26, "采暖系统示意图", 5.0)
    d.paper_rect(160, 200, 100, 22, "S-HVAC", 0.35)
    d.paper_text(210, 211, "换热站 / 壁挂炉", 2.8)
    d.paper_line(180, 50, 180, 200, "S-HVAC", 0.5)
    d.paper_line(240, 50, 240, 200, "S-HVAC", 0.5)
    d.paper_text(180, 44, "供", 2.4)
    d.paper_text(240, 44, "回", 2.4)
    for i in range(m.spec.floors):
        y = 190 - i * min(16, 140 / max(m.spec.floors, 1))
        d.paper_line(180, y, 240, y, "S-HVAC", 0.3)
        d.paper_text(252, y, f"{i+1}F 散热器", 2.2, "s", "S-HVAC")
    return d


def _vent_plan(m: BuildingModel, number: str) -> Drawing:
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}通风平面图", "通风")
    for r in rooms_of(m, m.typical_floor(), {"卫生间", "厨房", "设备", "车库"}):
        d.rect(r.cx - 0.4, r.cy - 0.3, 0.8, 0.6, "S-VENT", 0.25, fill="#bbf7d0")
        d.text(r.cx, r.cy, "排风口", "S-VENT", 1.6)
        d.line(r.cx, r.cy, r.x + r.w, r.cy, "S-VENT", 0.25)
    shafts = rooms_of(m, m.typical_floor(), {"竖井", "楼梯"})
    for s in shafts:
        d.rect(s.x + 0.1, s.y + 0.1, 0.8, 0.8, "S-VENT", 0.3)
        d.text(s.x + 0.5, s.y + 0.5, "风井", "S-VENT", 1.5)
    d.text(m.length / 2, m.width + 3.5, "卫生间机械排风，走廊补风示意", "S-VENT", 2.4)
    return d


def _ac_plan(m: BuildingModel, number: str) -> Drawing:
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}空调平面图", "通风")
    for r in m.plans[m.typical_floor()].rooms:
        if r.kind in ("竖井", "电梯", "楼梯", "卫生间") or r.area < 8:
            continue
        n = max(1, int(r.area / 40))
        for i in range(n):
            x = r.x + (i + 0.5) * r.w / n
            y = r.y + r.h - 0.7
            d.rect(x - 0.7, y - 0.25, 1.4, 0.5, "S-HVAC", 0.2, fill="#99f6e4")
            d.text(x, y, "FCU", "S-HVAC", 1.6)
    d.text(m.length / 2, m.width + 3.5, "风机盘管 + 新风示意（冷源见屋顶）", "S-HVAC", 2.4)
    return d


def _hydrant_plan(m: BuildingModel, number: str) -> Drawing:
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}室内消火栓平面图", "消防")
    pts = place_along(corridor_polyline(m, m.typical_floor()), 18.0)
    if not pts:
        pts = [(2, 2), (m.length - 2, 2), (m.length - 2, m.width - 2), (2, m.width - 2)]
    # also corners
    pts = pts + [(1.2, 1.2), (m.length - 1.2, 1.2), (m.length - 1.2, m.width - 1.2), (1.2, m.width - 1.2)]
    seen = set()
    for x, y in pts:
        key = (round(x, 0), round(y, 0))
        if key in seen:
            continue
        seen.add(key)
        d.rect(x - 0.35, y - 0.25, 0.7, 0.5, "S-FIRE", 0.25, fill="#fecaca")
        d.text(x, y, "消", "S-FIRE", 2.0)
    d.text(m.length / 2, m.width + 3.5, "室内消火栓间距按 ≤30m 示意布置", "S-FIRE", 2.4)
    return d


def _sprinkler_plan(m: BuildingModel, number: str) -> Drawing:
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}自动喷水灭火平面图", "消防")
    for x, y in grid_points(m, step=3.4, inset=1.7):
        d.circle(x, y, 0.16, "S-FIRE", 0.2)
        d.line(x - 0.16, y - 0.16, x + 0.16, y + 0.16, "S-FIRE", 0.12)
        d.line(x - 0.16, y + 0.16, x + 0.16, y - 0.16, "S-FIRE", 0.12)
    d.text(m.length / 2, m.width + 3.5, "喷头按中危险级Ⅰ级 3.4m 间距示意", "S-FIRE", 2.4)
    return d


def _alarm_plan(m: BuildingModel, number: str) -> Drawing:
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}火灾自动报警平面图", "消防")
    for r in m.plans[m.typical_floor()].rooms:
        if r.area < 6:
            continue
        d.circle(r.cx, r.cy + 0.4, 0.18, "S-FIRE", 0.2, fill="#fecaca")
        d.text(r.cx, r.cy + 0.4, "感", "S-FIRE", 1.4)
        if r.kind in ("走廊", "门厅", "楼梯"):
            d.rect(r.x + 0.3, r.cy - 0.2, 0.4, 0.3, "S-FIRE", 0.2)
            d.text(r.x + 1.1, r.cy, "声光", "S-FIRE", 1.5)
    d.text(m.length / 2, m.width + 3.5, "感烟探测器 + 声光警报器示意", "S-FIRE", 2.4)
    return d


def _smoke_plan(m: BuildingModel, number: str) -> Drawing:
    d = _base_plan(m, number, f"{m.floor_name(m.typical_floor())}防排烟平面图", "消防")
    for r in rooms_of(m, m.typical_floor(), {"楼梯", "走廊", "门厅", "车库"}):
        d.rect(r.cx - 0.6, r.cy - 0.35, 1.2, 0.7, "S-FIRE", 0.25, fill="#fed7aa")
        d.text(r.cx, r.cy, "排烟口", "S-FIRE", 1.6)
    for r in rooms_of(m, m.typical_floor(), {"楼梯"}):
        d.text(r.cx, r.y + 0.4, "加压送风", "S-FIRE", 1.6)
    d.text(m.length / 2, m.width + 3.5, "楼梯间加压送风、走道机械排烟示意", "S-FIRE", 2.4)
    return d
