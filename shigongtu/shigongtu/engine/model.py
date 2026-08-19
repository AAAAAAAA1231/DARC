from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


PRESETS: dict[str, dict[str, Any]] = {
    "办公楼": {
        "floor_height": 3.6,
        "span_x": 8.4,
        "span_y": 8.4,
        "aspect": 2.0,
        "structure": "框架",
        "occupancy": 8.0,
        "layout": "office",
        "window_w": 1.8,
        "window_h": 1.8,
        "sill": 0.9,
    },
    "住宅": {
        "floor_height": 2.9,
        "span_x": 4.2,
        "span_y": 3.9,
        "aspect": 2.4,
        "structure": "框剪",
        "occupancy": 35.0,
        "layout": "residential",
        "window_w": 1.5,
        "window_h": 1.5,
        "sill": 0.9,
    },
    "商业": {
        "floor_height": 4.5,
        "span_x": 8.4,
        "span_y": 8.4,
        "aspect": 1.8,
        "structure": "框架",
        "occupancy": 4.0,
        "layout": "commercial",
        "window_w": 2.4,
        "window_h": 2.4,
        "sill": 0.3,
    },
    "厂房": {
        "floor_height": 8.0,
        "span_x": 12.0,
        "span_y": 9.0,
        "aspect": 2.2,
        "structure": "钢结构",
        "occupancy": 20.0,
        "layout": "factory",
        "window_w": 3.0,
        "window_h": 2.4,
        "sill": 1.2,
    },
    "学校": {
        "floor_height": 3.6,
        "span_x": 9.0,
        "span_y": 8.4,
        "aspect": 3.0,
        "structure": "框架",
        "occupancy": 1.4,
        "layout": "school",
        "window_w": 1.8,
        "window_h": 1.8,
        "sill": 0.9,
    },
    "医院": {
        "floor_height": 3.6,
        "span_x": 8.1,
        "span_y": 8.1,
        "aspect": 2.4,
        "structure": "框剪",
        "occupancy": 10.0,
        "layout": "hospital",
        "window_w": 1.5,
        "window_h": 1.5,
        "sill": 0.9,
    },
    "酒店": {
        "floor_height": 3.3,
        "span_x": 8.0,
        "span_y": 4.2,
        "aspect": 2.8,
        "structure": "框剪",
        "occupancy": 18.0,
        "layout": "hotel",
        "window_w": 1.5,
        "window_h": 1.5,
        "sill": 0.9,
    },
}

STRUCTURES = ["框架", "框剪", "剪力墙", "砖混", "钢结构", "排架"]
CLIMATES = ["严寒", "寒冷", "夏热冬冷", "夏热冬暖", "温和"]
FIRE_RATINGS = ["一级", "二级", "三级", "四级"]
FOUNDATIONS = ["独立基础", "条形基础", "筏板基础", "桩基础"]


def _f(v: Any, default: float) -> float:
    if v is None or v == "":
        return default
    try:
        return float(str(v).replace("㎡", "").replace("m²", "").replace("m", "").strip())
    except ValueError:
        return default


def _i(v: Any, default: int) -> int:
    if v is None or v == "":
        return default
    try:
        return int(float(str(v).strip()))
    except ValueError:
        return default


@dataclass
class BuildingSpec:
    name: str = "××办公楼工程"
    location: str = "某市"
    client: str = ""
    designer: str = "施工图生成器"
    building_type: str = "办公楼"
    floors: int = 6
    basement: int = 0
    floor_area: float = 1200.0
    total_area: float = 0.0
    floor_height: float = 0.0
    length: float = 0.0
    width: float = 0.0
    span_x: float = 0.0
    span_y: float = 0.0
    structure: str = ""
    seismic: str = "7度"
    fire_rating: str = "二级"
    climate: str = "夏热冬冷"
    foundation: str = ""
    notes: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BuildingSpec":
        t = str(data.get("building_type") or "办公楼")
        if t not in PRESETS:
            t = "办公楼"
        p = PRESETS[t]
        floors = max(1, _i(data.get("floors"), 6))
        basement = max(0, min(3, _i(data.get("basement"), 0)))
        floor_area = _f(data.get("floor_area"), 0.0)
        total_area = _f(data.get("total_area"), 0.0)
        if floor_area <= 0 and total_area > 0:
            floor_area = total_area / max(floors + basement * 0.8, 1)
        if floor_area <= 0:
            floor_area = 1200.0 if t != "住宅" else 640.0
        if total_area <= 0:
            total_area = floor_area * floors + floor_area * 0.85 * basement
        spec = cls(
            name=str(data.get("name") or "××工程").strip() or "××工程",
            location=str(data.get("location") or "某市"),
            client=str(data.get("client") or ""),
            designer=str(data.get("designer") or "施工图生成器"),
            building_type=t,
            floors=floors,
            basement=basement,
            floor_area=floor_area,
            total_area=total_area,
            floor_height=_f(data.get("floor_height"), 0.0) or float(p["floor_height"]),
            length=_f(data.get("length"), 0.0),
            width=_f(data.get("width"), 0.0),
            span_x=_f(data.get("span_x"), 0.0) or float(p["span_x"]),
            span_y=_f(data.get("span_y"), 0.0) or float(p["span_y"]),
            structure=str(data.get("structure") or p["structure"]),
            seismic=str(data.get("seismic") or "7度"),
            fire_rating=str(data.get("fire_rating") or ("一级" if floors >= 10 or floor_area >= 2000 else "二级")),
            climate=str(data.get("climate") or "夏热冬冷"),
            foundation=str(data.get("foundation") or ""),
            notes=str(data.get("notes") or ""),
        )
        if not spec.foundation:
            if spec.floors >= 12 or spec.basement >= 2:
                spec.foundation = "桩基础"
            elif spec.floors >= 7 or spec.basement >= 1:
                spec.foundation = "筏板基础"
            elif spec.structure in ("砖混",):
                spec.foundation = "条形基础"
            elif spec.structure in ("钢结构", "排架"):
                spec.foundation = "独立基础"
            else:
                spec.foundation = "独立基础"
        return spec


def axis_letter(j: int) -> str:
    letters = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    if j < len(letters):
        return letters[j]
    return f"{letters[j % len(letters)]}{j // len(letters)}"


@dataclass
class Room:
    name: str
    kind: str
    x: float
    y: float
    w: float
    h: float
    floor: int

    @property
    def area(self) -> float:
        return self.w * self.h

    @property
    def cx(self) -> float:
        return self.x + self.w / 2

    @property
    def cy(self) -> float:
        return self.y + self.h / 2

    def bbox(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.x + self.w, self.y + self.h


@dataclass
class Wall:
    x1: float
    y1: float
    x2: float
    y2: float
    thickness: float
    exterior: bool
    floor: int


@dataclass
class Opening:
    kind: str  # door / window / shutter
    x1: float
    y1: float
    x2: float
    y2: float
    width: float
    floor: int
    swing: str = "left"  # left/right/none


@dataclass
class Column:
    i: int
    j: int
    x: float
    y: float
    size: float  # m


@dataclass
class FloorPlan:
    floor: int
    name: str
    rooms: list[Room] = field(default_factory=list)
    walls: list[Wall] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)


@dataclass
class BuildingModel:
    spec: BuildingSpec
    length: float = 0.0
    width: float = 0.0
    nx: int = 0
    ny: int = 0
    axes_x: list[float] = field(default_factory=list)
    axes_y: list[float] = field(default_factory=list)
    columns: list[Column] = field(default_factory=list)
    plans: dict[int, FloorPlan] = field(default_factory=dict)
    n_stairs: int = 2
    n_elevators: int = 1
    col_size: float = 0.5
    beam_b: float = 0.3
    beam_h: float = 0.6
    slab: float = 0.12
    warnings: list[str] = field(default_factory=list)
    notes: dict[str, list[str]] = field(default_factory=dict)

    @property
    def height(self) -> float:
        return self.spec.floors * self.spec.floor_height + 1.2

    @property
    def actual_floor_area(self) -> float:
        return self.length * self.width

    @property
    def actual_total_area(self) -> float:
        return self.actual_floor_area * self.spec.floors + self.actual_floor_area * 0.9 * self.spec.basement

    def floor_name(self, fl: int) -> str:
        if fl < 0:
            return f"地下{-fl}层"
        if fl == 1:
            return "首层"
        if fl == self.spec.floors:
            return "顶层" if self.spec.floors > 2 else "二层"
        return f"{fl}层"

    def typical_floor(self) -> int:
        if self.spec.floors >= 3:
            return 2
        return 1

    def floor_list(self) -> list[int]:
        return list(range(-self.spec.basement, 0)) + list(range(1, self.spec.floors + 1))

    def summary(self) -> dict[str, Any]:
        s = self.spec
        return {
            "name": s.name,
            "building_type": s.building_type,
            "location": s.location,
            "floors": s.floors,
            "basement": s.basement,
            "length": round(self.length, 2),
            "width": round(self.width, 2),
            "height": round(self.height, 2),
            "span_x": s.span_x,
            "span_y": s.span_y,
            "nx": self.nx,
            "ny": self.ny,
            "floor_area": round(self.actual_floor_area, 1),
            "total_area": round(self.actual_total_area, 1),
            "floor_height": s.floor_height,
            "structure": s.structure,
            "foundation": s.foundation,
            "seismic": s.seismic,
            "fire_rating": s.fire_rating,
            "climate": s.climate,
            "n_stairs": self.n_stairs,
            "n_elevators": self.n_elevators,
            "col_size_mm": int(self.col_size * 1000),
            "beam": f"{int(self.beam_b*1000)}×{int(self.beam_h*1000)}",
            "slab_mm": int(self.slab * 1000),
        }


def seismic_degree(text: str) -> int:
    for n in (9, 8, 7, 6):
        if str(n) in str(text):
            return n
    return 7


def column_size(spec: BuildingSpec) -> float:
    n = spec.floors + spec.basement
    if spec.structure in ("钢结构", "排架"):
        return 0.4 if n <= 2 else 0.5
    if n <= 4:
        return 0.45
    if n <= 8:
        return 0.5
    if n <= 12:
        return 0.6
    if n <= 18:
        return 0.7
    return 0.8


def beam_size(spec: BuildingSpec, span: float) -> tuple[float, float]:
    h = max(0.4, min(0.9, span / 12))
    b = 0.25 if h < 0.5 else 0.3 if h < 0.7 else 0.35
    if spec.structure in ("钢结构", "排架"):
        return 0.3, max(0.4, span / 15)
    return b, round(h * 20) / 20


def fit_grid(spec: BuildingSpec) -> tuple[float, float, int, int]:
    target = max(80.0, spec.floor_area)
    sx, sy = spec.span_x, spec.span_y
    if spec.length > 1 and spec.width > 1:
        nx = max(2, round(spec.length / sx))
        ny = max(2, round(spec.width / sy))
        return nx * sx, ny * sy, nx, ny
    aspect = PRESETS[spec.building_type]["aspect"]
    length = math.sqrt(target * aspect)
    width = target / length
    nx = max(2, round(length / sx))
    ny = max(2, round(width / sy))
    best = None
    for dx in range(-3, 4):
        for dy in range(-2, 3):
            a, b = nx + dx, ny + dy
            if a < 2 or b < 2:
                continue
            L, W = a * sx, b * sy
            err = abs(L * W - target) / target
            score = err + 0.02 * abs(L / W - aspect)
            if best is None or score < best[0]:
                best = (score, L, W, a, b)
    assert best is not None
    return best[1], best[2], best[3], best[4]


def n_elevators(spec: BuildingSpec, floor_area: float) -> int:
    if spec.building_type == "厂房" and spec.floors <= 2:
        return 0
    if spec.floors < 4 and floor_area < 800:
        return 0 if spec.building_type == "住宅" and spec.floors <= 6 else 1
    pop = floor_area / PRESETS[spec.building_type]["occupancy"] * 0.6
    n = max(1, round(pop / 250))
    if spec.floors >= 12:
        n = max(n, 2)
    if spec.building_type in ("医院", "酒店") :
        n = max(n, 2)
    return min(6, n)


def n_stairs(spec: BuildingSpec, length: float, width: float, floor_area: float) -> int:
    # GB 55037 / GB 50016 schematic: two stairs as default except tiny single-stair houses
    if spec.building_type == "住宅" and spec.floors <= 6 and floor_area < 500 and max(length, width) < 30:
        return 1
    n = 2
    travel = max(length, width)
    if travel > 50 or floor_area > 2000:
        n = 3
    if travel > 80 or floor_area > 4000:
        n = 4
    if spec.floors >= 10:
        n = max(n, 2)
    return n
