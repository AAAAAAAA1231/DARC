from __future__ import annotations

from .model import (
    BuildingModel,
    BuildingSpec,
    Column,
    FloorPlan,
    Opening,
    Room,
    Wall,
    axis_letter,
    beam_size,
    column_size,
    fit_grid,
    n_elevators,
    n_stairs,
    seismic_degree,
)

CIRC = {"走廊", "门厅", "电梯厅", "楼梯", "电梯"}


def build_model(spec: BuildingSpec) -> BuildingModel:
    length, width, nx, ny = fit_grid(spec)
    m = BuildingModel(spec=spec, length=length, width=width, nx=nx, ny=ny)
    m.axes_x = [i * spec.span_x for i in range(nx + 1)]
    m.axes_y = [j * spec.span_y for j in range(ny + 1)]
    m.col_size = column_size(spec)
    m.beam_b, m.beam_h = beam_size(spec, max(spec.span_x, spec.span_y))
    m.slab = 0.12 if spec.floors <= 8 else 0.13
    if spec.building_type == "厂房":
        m.slab = 0.18
    m.n_elevators = n_elevators(spec, m.actual_floor_area)
    m.n_stairs = n_stairs(spec, length, width, m.actual_floor_area)
    for i, x in enumerate(m.axes_x):
        for j, y in enumerate(m.axes_y):
            m.columns.append(Column(i=i, j=j, x=x, y=y, size=m.col_size))
    layout_kind = {
        "办公楼": layout_office,
        "住宅": layout_residential,
        "商业": layout_commercial,
        "厂房": layout_factory,
        "学校": layout_school,
        "医院": layout_hospital,
        "酒店": layout_hotel,
    }.get(spec.building_type, layout_office)
    for fl in m.floor_list():
        rooms = layout_kind(m, fl)
        if fl < 0:
            rooms = layout_basement(m, fl, rooms)
        plan = FloorPlan(floor=fl, name=m.floor_name(fl), rooms=rooms)
        plan.walls = walls_from_rooms(m, rooms, fl)
        plan.openings = openings_from_rooms(m, rooms, fl)
        m.plans[fl] = plan
    _warnings(m)
    _design_notes(m)
    return m


def _rect(name: str, kind: str, x: float, y: float, w: float, h: float, fl: int) -> Room:
    return Room(name=name, kind=kind, x=x, y=y, w=max(0.8, w), h=max(0.8, h), floor=fl)


def layout_office(m: BuildingModel, fl: int) -> list[Room]:
    L, W = m.length, m.width
    sx, sy = m.spec.span_x, m.spec.span_y
    rooms: list[Room] = []
    core_w = min(sx, max(7.2, 2.8 + 2.4 * max(1, m.n_elevators) + 3.6))
    core_w = min(core_w, L * 0.35)
    core_h = min(W - 2.0, max(8.0, sy * min(2, m.ny)))
    core_x = (L - core_w) / 2
    core_y = (W - core_h) / 2
    stair_w, stair_h = 2.7, min(6.6, core_h - 0.4)
    rooms.append(_rect("楼梯间-1", "楼梯", core_x + 0.15, core_y + 0.2, stair_w, stair_h, fl))
    if m.n_stairs >= 2:
        rooms.append(_rect("楼梯间-2", "楼梯", L - 3.1, 0.2, 2.9, min(6.6, W - 0.4), fl))
    if m.n_stairs >= 3:
        rooms.append(_rect("楼梯间-3", "楼梯", 0.2, W - 6.8, 2.9, 6.6, fl))
    ex = core_x + stair_w + 0.3
    if m.n_elevators:
        ew = min(2.4 * m.n_elevators, core_w - stair_w - 1.0)
        rooms.append(_rect("电梯", "电梯", ex, core_y + 0.2, max(2.2, ew), 2.6, fl))
        rooms.append(_rect("电梯厅", "电梯厅", ex, core_y + 2.9, max(2.2, ew), 2.2, fl))
        ex += max(2.2, ew) + 0.15
    rooms.append(_rect("男卫", "卫生间", core_x + 0.15, core_y + core_h - 3.2, min(3.3, core_w / 2 - 0.2), 3.0, fl))
    rooms.append(_rect("女卫", "卫生间", core_x + core_w / 2, core_y + core_h - 3.2, min(3.3, core_w / 2 - 0.2), 3.0, fl))
    rooms.append(_rect("强电井", "竖井", ex, core_y + 5.4, 1.2, 1.4, fl))
    rooms.append(_rect("弱电井", "竖井", ex + 1.35, core_y + 5.4, 1.1, 1.4, fl))
    rooms.append(_rect("水井", "竖井", ex + 2.6, core_y + 5.4, 1.1, 1.4, fl))
    corr_h = 2.2
    corr_y = max(3.0, min(core_y - 0.2, W / 2 - corr_h / 2))
    rooms.append(_rect("走廊", "走廊", 0.15, corr_y, L - 0.3, corr_h, fl))
    south_h = corr_y - 0.15
    north_y = corr_y + corr_h
    north_h = W - 0.15 - north_y
    if fl == 1:
        hall_w = min(12.0, L * 0.28)
        rooms.append(_rect("门厅", "门厅", (L - hall_w) / 2, 0.15, hall_w, max(4.5, south_h), fl))
        rooms.append(_rect("值班室", "办公", 0.15, 0.15, min(6.0, (L - hall_w) / 2 - 0.4), max(3.6, min(south_h, 4.8)), fl))
        rooms.append(_rect("开敞办公", "办公", (L + hall_w) / 2 + 0.2, 0.15, L - (L + hall_w) / 2 - 0.35, south_h, fl))
        if m.spec.floors >= 1:
            rooms.append(_rect("配电室", "设备", L - 7.2, north_y, 7.05, min(4.5, north_h), fl))
            rooms.append(_rect("开敞办公", "办公", 0.15, north_y, L - 7.5, north_h, fl))
    else:
        rooms.append(_rect("开敞办公", "办公", 0.15, 0.15, L - 0.3, south_h, fl))
        rooms.append(_rect("开敞办公", "办公", 0.15, north_y, L - 0.3, north_h, fl))
    if fl == m.spec.floors:
        rooms.append(_rect("空调机房", "设备", 0.15, north_y, min(8.4, L * 0.2), min(5.0, north_h), fl))
    return _clip_rooms(rooms, L, W)


def layout_residential(m: BuildingModel, fl: int) -> list[Room]:
    L, W = m.length, m.width
    rooms: list[Room] = []
    core_w = 4.8 if m.n_elevators else 3.3
    core_h = min(W, 8.4)
    core_x = (L - core_w) / 2
    core_y = (W - core_h) / 2
    rooms.append(_rect("楼梯间", "楼梯", core_x + 0.1, core_y + 0.1, 2.7, min(6.6, core_h - 0.2), fl))
    if m.n_elevators:
        rooms.append(_rect("电梯", "电梯", core_x + 2.9, core_y + 0.1, 1.8, 2.4, fl))
        rooms.append(_rect("电梯厅", "电梯厅", core_x + 2.9, core_y + 2.6, 1.8, 2.0, fl))
    rooms.append(_rect("前室", "走廊", core_x, core_y + core_h - 2.2, core_w, 2.1, fl))
    if m.n_stairs >= 2:
        rooms.append(_rect("楼梯间-2", "楼梯", L - 3.0, 0.15, 2.85, 6.4, fl))
    unit_w = (L - core_w) / 2 - 0.2
    # 2 or 4 units
    four = W >= 12 and unit_w >= 9
    def unit(tag: str, x: float, y: float, w: float, h: float) -> None:
        ky = 3.0
        by = 2.4
        rooms.append(_rect(f"{tag}客厅", "客厅", x, y, w * 0.55, h - by - 0.1, fl))
        rooms.append(_rect(f"{tag}卧室1", "卧室", x + w * 0.55 + 0.1, y + h * 0.42, w * 0.45 - 0.1, h * 0.58 - by, fl))
        rooms.append(_rect(f"{tag}卧室2", "卧室", x + w * 0.55 + 0.1, y, w * 0.45 - 0.1, h * 0.4, fl))
        rooms.append(_rect(f"{tag}厨房", "厨房", x, y + h - by, w * 0.42, by - 0.05, fl))
        rooms.append(_rect(f"{tag}卫生间", "卫生间", x + w * 0.42 + 0.1, y + h - by, w * 0.28, by - 0.05, fl))
        rooms.append(_rect(f"{tag}阳台", "阳台", x + w * 0.72, y + h - by, w * 0.28 - 0.05, by - 0.05, fl))
        _ = ky
    if four:
        uh = (W - 0.3) / 2
        unit("A-", 0.15, 0.15, unit_w, uh)
        unit("B-", core_x + core_w + 0.05, 0.15, unit_w, uh)
        unit("C-", 0.15, uh + 0.2, unit_w, W - uh - 0.35)
        unit("D-", core_x + core_w + 0.05, uh + 0.2, unit_w, W - uh - 0.35)
    else:
        unit("A-", 0.15, 0.15, unit_w, W - 0.3)
        unit("B-", core_x + core_w + 0.05, 0.15, unit_w, W - 0.3)
    return _clip_rooms(rooms, L, W)


def layout_commercial(m: BuildingModel, fl: int) -> list[Room]:
    L, W = m.length, m.width
    rooms: list[Room] = []
    rooms.append(_rect("楼梯间-1", "楼梯", 0.2, 0.2, 2.9, 6.6, fl))
    rooms.append(_rect("楼梯间-2", "楼梯", L - 3.1, W - 6.8, 2.9, 6.6, fl))
    if m.n_elevators:
        rooms.append(_rect("电梯", "电梯", 3.3, 0.2, 2.4 * m.n_elevators, 2.6, fl))
        rooms.append(_rect("电梯厅", "电梯厅", 3.3, 2.9, 2.4 * m.n_elevators, 2.4, fl))
    rooms.append(_rect("公共卫生间", "卫生间", 0.2, W - 4.4, 6.5, 4.2, fl))
    rooms.append(_rect("走廊", "走廊", 0.2, W / 2 - 1.2, L - 0.4, 2.4, fl))
    if fl == 1:
        rooms.append(_rect("门厅", "门厅", L * 0.3, 0.2, L * 0.4, min(8.0, W * 0.35), fl))
        n_shop = max(4, m.nx)
        sw = (L - 0.4) / n_shop
        for i in range(n_shop):
            rooms.append(_rect(f"商铺{i+1}", "商铺", 0.2 + i * sw, W / 2 + 1.3, sw - 0.1, W / 2 - 1.5, fl))
        rooms.append(_rect("营业厅", "营业", 0.2, 0.2, L - 0.4, W / 2 - 1.5, fl))
    else:
        rooms.append(_rect("营业厅", "营业", 0.2, 0.2, L - 0.4, W / 2 - 1.5, fl))
        rooms.append(_rect("营业厅", "营业", 0.2, W / 2 + 1.3, L - 0.4, W / 2 - 1.5, fl))
    return _clip_rooms(rooms, L, W)


def layout_factory(m: BuildingModel, fl: int) -> list[Room]:
    L, W = m.length, m.width
    rooms: list[Room] = []
    office_w = min(9.0, m.spec.span_x)
    rooms.append(_rect("生产车间", "车间", office_w + 0.2, 0.15, L - office_w - 0.35, W - 0.3, fl))
    rooms.append(_rect("办公室", "办公", 0.15, 0.15, office_w, min(6.0, W * 0.35), fl))
    rooms.append(_rect("值班室", "办公", 0.15, min(6.2, W * 0.35) + 0.15, office_w, 3.3, fl))
    rooms.append(_rect("卫生间", "卫生间", 0.15, W - 4.0, office_w * 0.55, 3.85, fl))
    rooms.append(_rect("配电室", "设备", 0.15 + office_w * 0.58, W - 4.0, office_w * 0.4, 3.85, fl))
    rooms.append(_rect("楼梯间", "楼梯", 0.15, W * 0.45, 2.7, 5.4, fl))
    if m.n_stairs >= 2:
        rooms.append(_rect("楼梯间-2", "楼梯", L - 3.0, W - 6.6, 2.85, 6.4, fl))
    return _clip_rooms(rooms, L, W)


def layout_school(m: BuildingModel, fl: int) -> list[Room]:
    L, W = m.length, m.width
    rooms: list[Room] = []
    rooms.append(_rect("楼梯间-1", "楼梯", 0.15, 0.15, 3.2, 7.2, fl))
    rooms.append(_rect("楼梯间-2", "楼梯", L - 3.35, 0.15, 3.2, 7.2, fl))
    rooms.append(_rect("走廊", "走廊", 0.15, 7.5, L - 0.3, 2.4, fl))
    rooms.append(_rect("卫生间", "卫生间", 3.5, 0.15, 5.4, 4.2, fl))
    if m.n_elevators:
        rooms.append(_rect("电梯", "电梯", 9.1, 0.15, 2.4, 2.6, fl))
    class_y = 10.05
    class_h = W - class_y - 0.15
    n_class = max(3, int((L - 0.4) / 9.0))
    cw = (L - 0.4) / n_class
    for i in range(n_class):
        name = "教室" if fl > 1 or i > 0 else "门厅"
        kind = "教室" if name == "教室" else "门厅"
        if fl == 1 and i == n_class // 2:
            name, kind = "门厅", "门厅"
        rooms.append(_rect(f"{name}{i+1}" if kind == "教室" else name, kind, 0.15 + i * cw, class_y, cw - 0.12, class_h, fl))
    if fl == 1:
        rooms.append(_rect("值班室", "办公", 3.5, 4.5, 4.2, 2.8, fl))
    return _clip_rooms(rooms, L, W)


def layout_hospital(m: BuildingModel, fl: int) -> list[Room]:
    L, W = m.length, m.width
    rooms: list[Room] = []
    rooms.append(_rect("楼梯间-1", "楼梯", 0.15, 0.15, 3.0, 6.6, fl))
    rooms.append(_rect("楼梯间-2", "楼梯", L - 3.15, 0.15, 3.0, 6.6, fl))
    if m.n_elevators:
        rooms.append(_rect("电梯", "电梯", 3.3, 0.15, min(2.4 * m.n_elevators, 7.2), 2.8, fl))
        rooms.append(_rect("电梯厅", "电梯厅", 3.3, 3.1, min(2.4 * m.n_elevators, 7.2), 2.2, fl))
    rooms.append(_rect("走廊", "走廊", 0.15, W / 2 - 1.3, L - 0.3, 2.6, fl))
    rooms.append(_rect("卫生间", "卫生间", L - 7.4, W - 4.4, 7.2, 4.2, fl))
    north = W / 2 + 1.4
    nh = W - north - 0.15
    south_h = W / 2 - 1.5
    n = max(4, m.nx)
    rw = (L - 0.4) / n
    for i in range(n):
        if fl == 1 and i in (n // 2, n // 2 - 1):
            continue
        rooms.append(_rect(f"病房{i+1}", "病房", 0.15 + i * rw, north, rw - 0.12, nh, fl))
        rooms.append(_rect(f"诊室{i+1}" if fl == 1 else f"办公室{i+1}", "办公", 0.15 + i * rw, 0.15, rw - 0.12, south_h, fl))
    if fl == 1:
        rooms.append(_rect("门厅", "门厅", L * 0.35, 0.15, L * 0.3, south_h, fl))
        rooms.append(_rect("护士站", "办公", L * 0.4, north, L * 0.2, min(4.5, nh), fl))
    else:
        rooms.append(_rect("护士站", "办公", L * 0.4, north, L * 0.2, min(4.5, nh), fl))
    return _clip_rooms(rooms, L, W)


def layout_hotel(m: BuildingModel, fl: int) -> list[Room]:
    L, W = m.length, m.width
    rooms: list[Room] = []
    rooms.append(_rect("楼梯间-1", "楼梯", 0.15, 0.15, 2.8, 6.4, fl))
    rooms.append(_rect("楼梯间-2", "楼梯", L - 2.95, 0.15, 2.8, 6.4, fl))
    if m.n_elevators:
        rooms.append(_rect("电梯", "电梯", 3.1, 0.15, 2.4 * max(1, m.n_elevators), 2.6, fl))
        rooms.append(_rect("电梯厅", "电梯厅", 3.1, 2.85, 2.4 * max(1, m.n_elevators), 2.2, fl))
    corr_h = 1.8
    corr_y = W / 2 - corr_h / 2
    rooms.append(_rect("走廊", "走廊", 0.15, corr_y, L - 0.3, corr_h, fl))
    rooms.append(_rect("卫生间-公共卫生间", "卫生间", L - 6.5, W - 3.8, 6.3, 3.6, fl))
    if fl == 1:
        rooms.append(_rect("门厅", "门厅", L * 0.25, 0.15, L * 0.5, corr_y - 0.2, fl))
        rooms.append(_rect("餐厅", "营业", 0.15, corr_y + corr_h, L * 0.45, W - (corr_y + corr_h) - 0.15, fl))
        rooms.append(_rect("厨房", "厨房", L * 0.47, corr_y + corr_h, L * 0.25, min(8.0, W - corr_y - corr_h - 0.15), fl))
    else:
        n = max(6, int(L / 4.2))
        rw = (L - 0.4) / n
        for i in range(n):
            rooms.append(_rect(f"客房S{i+1}", "客房", 0.15 + i * rw, 0.15, rw - 0.1, corr_y - 0.25, fl))
            rooms.append(_rect(f"客房N{i+1}", "客房", 0.15 + i * rw, corr_y + corr_h, rw - 0.1, W - corr_y - corr_h - 0.15, fl))
    return _clip_rooms(rooms, L, W)


def layout_basement(m: BuildingModel, fl: int, upper: list[Room]) -> list[Room]:
    L, W = m.length, m.width
    rooms = [r for r in upper if r.kind in ("楼梯", "电梯", "竖井")]
    rooms.append(_rect("汽车库", "车库", 0.2, 0.2, L - 8.5, W - 0.4, fl))
    rooms.append(_rect("消防水泵房", "设备", L - 8.2, 0.2, 8.0, 5.4, fl))
    rooms.append(_rect("生活水泵房", "设备", L - 8.2, 5.8, 8.0, 4.2, fl))
    rooms.append(_rect("变配电室", "设备", L - 8.2, 10.2, 8.0, min(6.0, W - 10.4), fl))
    if W > 18:
        rooms.append(_rect("人防物资库", "人防", 0.2, W - 7.2, min(18.0, L * 0.4), 7.0, fl))
    return _clip_rooms(rooms, L, W)


def _clip_rooms(rooms: list[Room], L: float, W: float) -> list[Room]:
    out = []
    for r in rooms:
        x = max(0.05, r.x)
        y = max(0.05, r.y)
        w = min(r.w, L - x - 0.05)
        h = min(r.h, W - y - 0.05)
        if w >= 0.8 and h >= 0.8:
            out.append(Room(r.name, r.kind, x, y, w, h, r.floor))
    return out


def walls_from_rooms(m: BuildingModel, rooms: list[Room], fl: int) -> list[Wall]:
    L, W = m.length, m.width
    walls = [
        Wall(0, 0, L, 0, 0.2, True, fl),
        Wall(0, W, L, W, 0.2, True, fl),
        Wall(0, 0, 0, W, 0.2, True, fl),
        Wall(L, 0, L, W, 0.2, True, fl),
    ]
    seen: set[tuple[float, float, float, float]] = set()
    for r in rooms:
        segs = [
            (r.x, r.y, r.x + r.w, r.y),
            (r.x, r.y + r.h, r.x + r.w, r.y + r.h),
            (r.x, r.y, r.x, r.y + r.h),
            (r.x + r.w, r.y, r.x + r.w, r.y + r.h),
        ]
        for x1, y1, x2, y2 in segs:
            key = tuple(round(v, 2) for v in (min(x1, x2), min(y1, y2), max(x1, x2), max(y1, y2)))
            if key in seen:
                continue
            if (abs(x1) < 0.08 and abs(x2) < 0.08) or (abs(x1 - L) < 0.08 and abs(x2 - L) < 0.08):
                continue
            if (abs(y1) < 0.08 and abs(y2) < 0.08) or (abs(y1 - W) < 0.08 and abs(y2 - W) < 0.08):
                continue
            seen.add(key)
            walls.append(Wall(x1, y1, x2, y2, 0.1, False, fl))
    return walls


def _overlap_1d(a1: float, a2: float, b1: float, b2: float) -> tuple[float, float] | None:
    lo, hi = max(min(a1, a2), min(b1, b2)), min(max(a1, a2), max(b1, b2))
    if hi - lo < 0.8:
        return None
    return lo, hi


def _shared_edge(a: Room, b: Room) -> tuple[float, float, float, float] | None:
    # horizontal shared
    if abs((a.y + a.h) - b.y) < 0.12 or abs((b.y + b.h) - a.y) < 0.12:
        ov = _overlap_1d(a.x, a.x + a.w, b.x, b.x + b.w)
        if ov:
            y = a.y + a.h if abs((a.y + a.h) - b.y) < 0.12 else a.y
            return ov[0], y, ov[1], y
    if abs((a.x + a.w) - b.x) < 0.12 or abs((b.x + b.w) - a.x) < 0.12:
        ov = _overlap_1d(a.y, a.y + a.h, b.y, b.y + b.h)
        if ov:
            x = a.x + a.w if abs((a.x + a.w) - b.x) < 0.12 else a.x
            return x, ov[0], x, ov[1]
    return None


def openings_from_rooms(m: BuildingModel, rooms: list[Room], fl: int) -> list[Opening]:
    L, W = m.length, m.width
    p = __import__("shigongtu.engine.model", fromlist=["PRESETS"]).PRESETS[m.spec.building_type]
    ww = float(p["window_w"])
    openings: list[Opening] = []
    circ = [r for r in rooms if r.kind in CIRC]
    if not circ:
        circ = rooms[:1]
    placed_door: set[str] = set()
    for r in rooms:
        if r.kind in CIRC:
            continue
        best = None
        for c in circ:
            e = _shared_edge(r, c)
            if e:
                best = e
                break
        if best is None:
            continue
        x1, y1, x2, y2 = best
        if abs(y1 - y2) < 0.05:
            mid = (x1 + x2) / 2
            dw = 1.0 if r.kind in ("楼梯", "门厅", "车间", "营业", "车库") else 0.9
            openings.append(Opening("door", mid - dw / 2, y1, mid + dw / 2, y1, dw, fl, "left"))
        else:
            mid = (y1 + y2) / 2
            dw = 0.9
            openings.append(Opening("door", x1, mid - dw / 2, x1, mid + dw / 2, dw, fl, "left"))
        placed_door.add(r.name)
    # main entrance
    if fl == 1:
        openings.append(Opening("door", L / 2 - 1.2, 0, L / 2 + 1.2, 0, 2.4, fl, "left"))
    # windows on exterior
    for r in rooms:
        if r.kind in ("竖井", "电梯", "楼梯"):
            continue
        edges = []
        if r.y < 0.3:
            edges.append(("h", r.x + 0.4, 0.0, r.x + r.w - 0.4))
        if abs(r.y + r.h - W) < 0.3:
            edges.append(("h", r.x + 0.4, W, r.x + r.w - 0.4))
        if r.x < 0.3:
            edges.append(("v", r.y + 0.4, 0.0, r.y + r.h - 0.4))
        if abs(r.x + r.w - L) < 0.3:
            edges.append(("v", r.y + 0.4, L, r.y + r.h - 0.4))
        for kind, a, pos, b in edges:
            span = b - a
            if span < 1.2:
                continue
            n = max(1, int(span / (ww + 1.2)))
            step = span / n
            for i in range(n):
                c = a + step * (i + 0.5)
                if kind == "h":
                    openings.append(Opening("window", c - ww / 2, pos, c + ww / 2, pos, ww, fl, "none"))
                else:
                    openings.append(Opening("window", pos, c - ww / 2, pos, c + ww / 2, ww, fl, "none"))
    return openings


def _warnings(m: BuildingModel) -> None:
    s = m.spec
    m.warnings = [
        "本图由参数化规则自动生成，深度相当于方案/初步设计，不能替代施工图审查、结构计算书和注册人员签章。",
        "墙体、梁柱、管线仅为示意布置，须按地质勘察、专业计算和现行规范深化后方可用于施工。",
        "消防、人防、幕墙、基坑、装配式等专项须另行编制；本工具不生成节点大样的全部索引。",
    ]
    if abs(m.actual_floor_area - s.floor_area) / max(s.floor_area, 1) > 0.12:
        m.warnings.append(
            f"单层面积按柱网取整后为 {m.actual_floor_area:.0f}㎡（输入 {s.floor_area:.0f}㎡），轴线尺寸已吸附到 {s.span_x}m×{s.span_y}m 柱网。"
        )
    if s.floors >= 7 and m.n_elevators < 1:
        m.warnings.append("七层及以上民用建筑应按规范设置电梯，请核对电梯数量。")
    deg = seismic_degree(s.seismic)
    if deg >= 8 and s.structure == "砖混":
        m.warnings.append("8度区不宜采用砖混结构，建议改为框架或框剪。")


def _design_notes(m: BuildingModel) -> None:
    s = m.spec
    sm = m.summary()
    m.notes = {
        "建筑": [
            f"本工程为{s.building_type}，{s.location}，地上{s.floors}层"
            + (f"、地下{s.basement}层" if s.basement else "")
            + f"，建筑高度约{m.height:.1f}m，总建筑面积约{sm['total_area']:.0f}㎡，耐火等级{s.fire_rating}。",
            f"平面按 {s.span_x}m×{s.span_y}m 柱网布置，平面外包尺寸 {m.length:.2f}m×{m.width:.2f}m。层高 {s.floor_height}m。",
            f"竖向交通：楼梯 {m.n_stairs} 部"
            + (f"，电梯 {m.n_elevators} 台。" if m.n_elevators else "。"),
            "设计依据（名称编号，正文以正式文本为准）：GB 55031-2022 民用建筑通用规范，GB 55037-2022 建筑防火通用规范，GB 50016-2014（2018年版）建筑设计防火规范，GB 55038 住宅项目规范（住宅时），GB 50352-2019 民用建筑设计统一标准。",
            "门窗、节能、无障碍、屋面防水、外墙保温须按节能计算书和当地标准图集深化。",
        ],
        "结构": [
            f"结构体系：{s.structure}；抗震设防烈度 {s.seismic}；基础拟采用{s.foundation}。",
            f"框架柱截面按层数经验取 {sm['col_size_mm']}×{sm['col_size_mm']}；主梁约 {sm['beam']}；楼板厚 {sm['slab_mm']}mm。以上尺寸仅为绘图用经验值，必须以计算书为准。",
            "设计依据：GB 55001-2021 工程结构通用规范，GB 55002-2021 建筑与市政工程抗震通用规范，GB 50009-2012 建筑结构荷载规范，GB 50010-2010（2024年版）混凝土结构设计规范，GB 50011-2010（2016年版）建筑抗震设计规范。",
            "混凝土强度、钢筋等级、基础埋深、桩型及沉降须根据地勘报告确定。",
        ],
        "给排水": [
            "生活给水采用市政压力/分区供水示意；热水及直饮水未单独出图。",
            "污废水立管结合卫生间、竖井布置，底层排出；屋面雨水外排。",
            "设计依据：GB 55020-2021 建筑给水排水与节水通用规范，GB 50015-2019 建筑给水排水设计标准。",
        ],
        "电气": [
            "负荷密度按建筑性质估算，配电室/强电井、照明、插座、防雷接地为系统示意。",
            "设计依据：GB 55024-2022 建筑电气与智能化通用规范，GB 51348-2019 民用建筑电气设计标准，GB 50057-2010 建筑物防雷设计规范。",
        ],
        "暖通": [
            f"气候区：{s.climate}。"
            + ("设集中/分户采暖示意。" if s.climate in ("严寒", "寒冷", "夏热冬冷") else "本气候区一般不强制集中采暖，本套仍给出采暖平面示意供核对。"),
            "设计依据：GB 55015-2021 建筑节能与可再生能源利用通用规范，GB 50736-2012 民用建筑供暖通风与空气调节设计规范。",
        ],
        "通风": [
            "卫生间、厨房、地下室、消防前室/楼梯间按规范设置排风或防排烟示意；办公/教室为新风+排风示意。",
            "防排烟系统与消防专业配合，风量未做计算。",
        ],
        "消防": [
            f"室内消火栓、自动喷水灭火、火灾自动报警、防排烟按{s.building_type}公共/居住建筑示意布置。",
            "设计依据：GB 55036-2022 消防设施通用规范，GB 50974-2014 消防给水及消火栓系统技术规范，GB 50084-2017 自动喷水灭火系统设计规范，GB 50116-2013 火灾自动报警系统设计规范。",
            "消防水池、泵房、高位水箱有效容积须计算确定。",
        ],
    }


def axis_labels(m: BuildingModel) -> tuple[list[str], list[str]]:
    xs = [str(i + 1) for i in range(len(m.axes_x))]
    ys = [axis_letter(j) for j in range(len(m.axes_y))]
    return xs, ys
