from __future__ import annotations

import math

from .canvas import ROOM_FILL, Drawing, north_arrow, scale_bar
from .layout import axis_labels
from .model import BuildingModel, FloorPlan, Opening, Room


def draw_grid(d: Drawing, m: BuildingModel, with_dim: bool = True) -> None:
    xs, ys = axis_labels(m)
    L, W = m.length, m.width
    for i, x in enumerate(m.axes_x):
        d.line(x, -1.2, x, W + 1.2, "S-AXIS", 0.16, "center")
        _bubble(d, x, -1.8, xs[i])
        _bubble(d, x, W + 1.8, xs[i])
    for j, y in enumerate(m.axes_y):
        d.line(-1.2, y, L + 1.2, y, "S-AXIS", 0.16, "center")
        _bubble(d, -1.8, y, ys[j])
        _bubble(d, L + 1.8, y, ys[j])
    if with_dim and len(m.axes_x) >= 2:
        d.dim_h(m.axes_x[0], m.axes_x[-1], -3.6, -0.2)
        for i in range(len(m.axes_x) - 1):
            d.dim_h(m.axes_x[i], m.axes_x[i + 1], -2.4, -0.15)
        d.dim_v(m.axes_y[0], m.axes_y[-1], -3.6, -0.2)
        for j in range(len(m.axes_y) - 1):
            d.dim_v(m.axes_y[j], m.axes_y[j + 1], -2.4, -0.15)


def _bubble(d: Drawing, x: float, y: float, label: str) -> None:
    d.circle(x, y, 0.45, "S-AXIS", 0.2)
    d.text(x, y, label, "S-AXIS", 2.2)


def draw_columns(d: Drawing, m: BuildingModel) -> None:
    s = m.col_size
    for c in m.columns:
        d.rect(c.x - s / 2, c.y - s / 2, s, s, "S-COL", 0.3, fill="#1e3a5f")


def draw_rooms(d: Drawing, plan: FloorPlan, label: bool = True) -> None:
    for r in plan.rooms:
        fill = ROOM_FILL.get(r.kind, "#f8fafc")
        d.rect(r.x, r.y, r.w, r.h, "S-HATCH", 0.05, fill=fill)
        if label and r.w * r.h >= 4:
            d.text(r.cx, r.cy + 0.35, r.name, "S-TEXT", 2.2)
            d.text(r.cx, r.cy - 0.45, f"{r.area:.1f}㎡", "S-TEXT", 1.8)


def draw_walls(d: Drawing, plan: FloorPlan) -> None:
    for w in plan.walls:
        if abs(w.y1 - w.y2) < 1e-6:
            t = w.thickness
            d.rect(min(w.x1, w.x2), w.y1 - t / 2, abs(w.x2 - w.x1), t, "S-WALL", 0.15, fill="#222" if w.exterior else "#444")
        else:
            t = w.thickness
            d.rect(w.x1 - t / 2, min(w.y1, w.y2), t, abs(w.y2 - w.y1), "S-WALL", 0.15, fill="#222" if w.exterior else "#444")


def draw_openings(d: Drawing, plan: FloorPlan) -> None:
    for op in plan.openings:
        if op.kind == "door":
            _door(d, op)
        else:
            _window(d, op)


def _door(d: Drawing, op: Opening) -> None:
    if abs(op.y1 - op.y2) < 1e-6:
        x1, x2, y = min(op.x1, op.x2), max(op.x1, op.x2), op.y1
        w = x2 - x1
        d.rect(x1, y - 0.08, w, 0.16, "S-DOOR", 0.1, fill="#f7f4ea")
        d.line(x1, y, x1, y + w, "S-DOOR", 0.25)
        # swing as quarter polyline
        pts = [(x1 + w * math.cos(a), y + w * math.sin(a)) for a in [i / 8 * math.pi / 2 for i in range(9)]]
        d.pline(pts, "S-DOOR", 0.16)
    else:
        y1, y2, x = min(op.y1, op.y2), max(op.y1, op.y2), op.x1
        w = y2 - y1
        d.rect(x - 0.08, y1, 0.16, w, "S-DOOR", 0.1, fill="#f7f4ea")
        d.line(x, y1, x + w, y1, "S-DOOR", 0.25)
        pts = [(x + w * math.sin(a), y1 + w * math.cos(a)) for a in [i / 8 * math.pi / 2 for i in range(9)]]
        d.pline(pts, "S-DOOR", 0.16)


def _window(d: Drawing, op: Opening) -> None:
    if abs(op.y1 - op.y2) < 1e-6:
        x1, x2, y = min(op.x1, op.x2), max(op.x1, op.x2), op.y1
        d.line(x1, y - 0.12, x2, y - 0.12, "S-WIND", 0.22)
        d.line(x1, y, x2, y, "S-WIND", 0.13)
        d.line(x1, y + 0.12, x2, y + 0.12, "S-WIND", 0.22)
        d.line(x1, y - 0.18, x1, y + 0.18, "S-WIND", 0.2)
        d.line(x2, y - 0.18, x2, y + 0.18, "S-WIND", 0.2)
    else:
        y1, y2, x = min(op.y1, op.y2), max(op.y1, op.y2), op.x1
        d.line(x - 0.12, y1, x - 0.12, y2, "S-WIND", 0.22)
        d.line(x, y1, x, y2, "S-WIND", 0.13)
        d.line(x + 0.12, y1, x + 0.12, y2, "S-WIND", 0.22)
        d.line(x - 0.18, y1, x + 0.18, y1, "S-WIND", 0.2)
        d.line(x - 0.18, y2, x + 0.18, y2, "S-WIND", 0.2)


def setup_plan(d: Drawing, m: BuildingModel) -> None:
    d.fit_plan(-5.5, -5.5, m.length + 5.5, m.width + 5.5)
    north_arrow(d, 50, 40)
    scale_bar(d, 48, 62)


def draw_architecture_plan(d: Drawing, m: BuildingModel, plan: FloorPlan) -> None:
    setup_plan(d, m)
    draw_rooms(d, plan)
    draw_grid(d, m)
    draw_walls(d, plan)
    draw_openings(d, plan)
    draw_columns(d, m)
    d.text(m.length / 2, m.width + 3.6, f"{plan.name}平面图  建筑面积 {m.actual_floor_area:.0f}㎡", "S-TEXT", 3.0)


def rooms_of(m: BuildingModel, fl: int, kinds: set[str] | None = None) -> list[Room]:
    plan = m.plans[fl]
    if not kinds:
        return plan.rooms
    return [r for r in plan.rooms if r.kind in kinds]


def corridor_polyline(m: BuildingModel, fl: int) -> list[tuple[float, float]]:
    cors = rooms_of(m, fl, {"走廊", "门厅", "电梯厅"})
    if not cors:
        return [(1, m.width / 2), (m.length - 1, m.width / 2)]
    c = max(cors, key=lambda r: r.w * r.h)
    return [(c.x + 0.4, c.cy), (c.x + c.w - 0.4, c.cy)]


def place_along(path: list[tuple[float, float]], spacing: float) -> list[tuple[float, float]]:
    if len(path) < 2:
        return path
    pts: list[tuple[float, float]] = []
    for i in range(len(path) - 1):
        x1, y1 = path[i]
        x2, y2 = path[i + 1]
        dist = math.hypot(x2 - x1, y2 - y1)
        n = max(1, int(dist / spacing))
        for k in range(n + 1):
            t = k / n
            pts.append((x1 + (x2 - x1) * t, y1 + (y2 - y1) * t))
    return pts


def grid_points(m: BuildingModel, step: float, inset: float = 1.5) -> list[tuple[float, float]]:
    pts = []
    x = inset
    while x < m.length - inset:
        y = inset
        while y < m.width - inset:
            pts.append((x, y))
            y += step
        x += step
    return pts
