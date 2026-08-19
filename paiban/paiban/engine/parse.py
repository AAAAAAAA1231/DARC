from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from paiban.config import RESOURCES


def load_catalog() -> dict[str, Any]:
    return json.loads((RESOURCES / "catalog.json").read_text(encoding="utf-8"))


@dataclass
class Opening:
    wall: str  # N S E W  (S=底边 y=0)
    offset: float
    width: float
    height: float = 2.1
    kind: str = "door"


@dataclass
class Room:
    name: str = "房间"
    kind: str = "客厅"
    width: float = 4.8
    depth: float = 6.0
    height: float = 2.8
    openings: list[Opening] = field(default_factory=list)
    source: str = "描述"

    @property
    def area(self) -> float:
        return self.width * self.depth

    @property
    def wall_area(self) -> float:
        peri = 2 * (self.width + self.depth)
        holes = sum(o.width * min(o.height, self.height) for o in self.openings)
        return max(0.0, peri * self.height - holes)


_DIM = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mm|毫米|cm|厘米|m|米)?\s*[xX×*乘by]+\s*(\d+(?:\.\d+)?)\s*(mm|毫米|cm|厘米|m|米)?",
    re.I,
)
_ROOM = re.compile(r"(客厅|起居室|主卧|次卧|卧室|餐厅|厨房|卫生间|洗手间|阳台|书房|玄关|走廊|过道|衣帽间|儿童房)")
_H = re.compile(r"(层高|净高|层高约?)\s*(\d+(?:\.\d+)?)\s*(m|米|mm)?")
_TILE = re.compile(r"(地砖|地板|墙砖|瓷砖|木地板|铝扣板|石膏板|吊顶)")


def _door_wall_from_text(text: str) -> str:
    if re.search(r"北(墙|侧)?.{0,6}门|门.{0,6}北|北门", text):
        return "N"
    if re.search(r"东(墙|侧)?.{0,6}门|门.{0,6}东|东门", text):
        return "E"
    if re.search(r"西(墙|侧)?.{0,6}门|门.{0,6}西|西门", text):
        return "W"
    return "S"


def _default_openings(kind: str, width: float, depth: float, project_type: str, door_wall: str = "S") -> list[Opening]:
    if kind in ("卫生间", "厨房"):
        dw = 0.70
    elif kind == "卧室":
        dw = 0.80
    elif kind == "走廊":
        dw = 0.90 if project_type == "新建" else 0.80
    else:
        dw = 0.90 if project_type == "新建" else 0.80
    span = width if door_wall in ("S", "N") else depth
    off = max(0.05 if kind == "走廊" else 0.15, (span - dw) / 2)
    dw = min(dw, max(0.5, span - 0.1))
    return [Opening(door_wall, off, dw, 2.1, "door")]


def _to_m(v: float, unit: str | None, peer: float = 0.0) -> float:
    u = (unit or "").lower()
    if u in ("mm", "毫米"):
        return v / 1000
    if u in ("cm", "厘米"):
        return v / 100
    if u in ("m", "米"):
        return v
    if v >= 50:
        return v / 1000
    if v >= 20 and peer >= 20:
        return v / 1000
    return v


def parse_description(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    cat = load_catalog()
    kind = "客厅"
    m = _ROOM.search(text)
    if m:
        kind = m.group(1)
        if kind in ("起居室",):
            kind = "客厅"
        if kind in ("洗手间",):
            kind = "卫生间"
        if kind in ("主卧", "次卧", "儿童房"):
            kind = "卧室"
        if kind in ("过道",):
            kind = "走廊"
    width, depth, height = 4.8, 6.0, 2.8
    dims = [(float(a), ua, float(b), ub) for a, ua, b, ub in _DIM.findall(text)]
    room_dim = None
    tile_dim = None
    for a, ua, b, ub in dims:
        wa, wb = _to_m(a, ua, b), _to_m(b, ub, a)
        pair = (max(wa, wb), min(wa, wb))
        if pair[0] >= 1.2:  # room
            if room_dim is None or pair[0] * pair[1] > room_dim[0] * room_dim[1]:
                room_dim = (wa, wb)
        elif 0.1 <= pair[0] <= 1.5:
            tile_dim = (wa, wb)
    if room_dim:
        width, depth = (room_dim[0], room_dim[1]) if room_dim[0] >= room_dim[1] else (room_dim[1], room_dim[0])
        # keep as parsed order if both similar
        width, depth = room_dim
    hm = _H.search(text)
    if hm:
        height = _to_m(float(hm.group(2)), hm.group(3))
        if height < 1.5:
            height = 2.8
    task = "floor"
    tm = _TILE.search(text)
    if tm:
        w = tm.group(1)
        if "墙" in w:
            task = "wall"
        elif "吊顶" in w or "石膏" in w or "铝扣" in w:
            task = "ceiling"
        elif "地" in w or "地板" in w:
            task = "floor"
    if any(k in text for k in ("家具", "沙发", "床", "衣柜", "布置")):
        if task == "floor" and "砖" not in text and "地板" not in text:
            task = "furniture"
    if "吊顶" in text:
        task = "ceiling"
    floor_tile = cat["tile_floors"][0]
    wall_tile = cat["tile_walls"][0]
    ceiling = cat["ceilings"][0]
    if tile_dim:
        tw, th = tile_dim
        def nearest(items, tw=tw, th=th):
            return min(items, key=lambda t: abs(t["w"] - tw) + abs(t["h"] - th))
        floor_tile = nearest(cat["tile_floors"])
        wall_tile = nearest(cat["tile_walls"])
        if abs(tw - 0.3) < 0.02 and abs(th - 0.3) < 0.02:
            ceiling = cat["ceilings"][1]
        if abs(tw - 0.6) < 0.02 and abs(th - 0.6) < 0.02 and "吊" in text:
            ceiling = cat["ceilings"][2]
    pattern = "straight"
    if any(k in text for k in ("工字", "错缝", "骑缝", "1/3")):
        pattern = "brick"
    if any(k in text for k in ("人字", "鱼骨", "herring")):
        pattern = "herringbone"
    if any(k in text for k in ("斜铺", "45")):
        pattern = "diagonal"
    if any(k in text for k in ("强化地板", "复合地板", "强化木")):
        floor_tile = next((t for t in cat["tile_floors"] if "强化" in (t.get("name") or "") + (t.get("kind") or "")), floor_tile)
        pattern = "laminate"
    display_name = kind
    if kind == "玄关":
        kind = "走廊"
        display_name = "玄关"
    project_type = "新建" if "新建" in text else "既有"
    known = ("客厅", "卧室", "餐厅", "厨房", "卫生间", "走廊", "阳台", "书房")
    room = Room(name=display_name, kind=kind if kind in known else "客厅", width=width, depth=depth, height=height, source="语言描述")
    room.openings = _default_openings(room.kind, width, depth, project_type, _door_wall_from_text(text))
    return {
        "room": room,
        "task": task,
        "floor_tile": floor_tile,
        "wall_tile": wall_tile,
        "ceiling": ceiling,
        "pattern": pattern,
        "project_type": project_type,
        "text": text,
    }


def parse_pdf_bytes(data: bytes) -> dict[str, Any]:
    from pypdf import PdfReader
    import io
    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    text = "\n".join(parts)
    info = parse_description(text if text.strip() else "客厅 4.8x6.0 地砖 800x800")
    info["room"].source = "PDF图纸"
    info["pdf_text"] = text[:2000]
    return info


def _doors_from_dxf_lines(msp, scale: float, x0: float, y0: float, w: float, d: float) -> list[Opening]:
    """Treat 0.60～2.20m LINEs that sit on a wall as door openings (CAD 常见画法)."""
    found: list[Opening] = []
    try:
        lines = list(msp.query("LINE"))
    except Exception:
        return found
    for e in lines:
        try:
            sx = float(e.dxf.start.x) * scale - x0
            sy = float(e.dxf.start.y) * scale - y0
            ex = float(e.dxf.end.x) * scale - x0
            ey = float(e.dxf.end.y) * scale - y0
        except Exception:
            continue
        length = math.hypot(ex - sx, ey - sy)
        if length < 0.60 or length > 2.20:
            continue
        mx, my = (sx + ex) / 2.0, (sy + ey) / 2.0
        tol = 0.20
        if abs(ey - sy) <= 0.15 and abs(my) <= tol and -0.05 <= mx <= w + 0.05:
            found.append(Opening("S", round(max(0.0, min(sx, ex)), 3), round(length, 3), 2.1, "door"))
        elif abs(ey - sy) <= 0.15 and abs(my - d) <= tol and -0.05 <= mx <= w + 0.05:
            found.append(Opening("N", round(max(0.0, min(sx, ex)), 3), round(length, 3), 2.1, "door"))
        elif abs(ex - sx) <= 0.15 and abs(mx) <= tol and -0.05 <= my <= d + 0.05:
            found.append(Opening("W", round(max(0.0, min(sy, ey)), 3), round(length, 3), 2.1, "door"))
        elif abs(ex - sx) <= 0.15 and abs(mx - w) <= tol and -0.05 <= my <= d + 0.05:
            found.append(Opening("E", round(max(0.0, min(sy, ey)), 3), round(length, 3), 2.1, "door"))
    best: dict[str, Opening] = {}
    for op in found:
        if op.wall not in best or op.width > best[op.wall].width:
            best[op.wall] = op
    return list(best.values())


def _dxf_unit_scale(ins: int, raw_w: float, raw_d: float) -> float:
    """住宅开间很少超过 40m。图纸数字 ≥50 时按毫米，避免把 5000×4000 当成米排爆内存。"""
    table = {0: 0.001, 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}
    scale = table.get(ins, 0.001)
    w, d = abs(raw_w) * scale, abs(raw_d) * scale
    if max(w, d) > 40 and max(abs(raw_w), abs(raw_d)) >= 50:
        return 0.001
    return scale


def parse_dxf_bytes(data: bytes) -> dict[str, Any]:
    import io
    import ezdxf
    from ezdxf import recover
    bio = io.BytesIO(data)
    try:
        doc = ezdxf.read(bio)
    except Exception:
        bio.seek(0)
        doc, _ = recover.read(bio)
    msp = doc.modelspace()
    ins = int(doc.header.get("$INSUNITS", 4) or 4)
    raw_polys = []
    for e in msp:
        try:
            t = e.dxftype()
        except Exception:
            continue
        pts = []
        if t == "LWPOLYLINE" and bool(e.closed):
            pts = [(float(p[0]), float(p[1])) for p in e.get_points("xy")]
        elif t == "POLYLINE" and bool(getattr(e, "is_closed", False)):
            pts = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in e.vertices]
        if len(pts) >= 3:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            w, d = max(xs) - min(xs), max(ys) - min(ys)
            if w > 0.5 and d > 0.5:
                raw_polys.append((w * d, w, d, pts, min(xs), min(ys)))
    if raw_polys:
        raw_polys.sort(reverse=True)
        _, rw, rd, _, _, _ = raw_polys[0]
        scale = _dxf_unit_scale(ins, rw, rd)
    else:
        scale = {0: 0.001, 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}.get(ins, 0.001)
    polys = []
    for _area, _rw, _rd, pts, xmin, ymin in raw_polys:
        pts_m = [(p[0] * scale, p[1] * scale) for p in pts]
        xs = [p[0] for p in pts_m]
        ys = [p[1] for p in pts_m]
        w, d = max(xs) - min(xs), max(ys) - min(ys)
        if w > 0.8 and d > 0.8:
            polys.append((w * d, w, d, pts_m, min(xs), min(ys)))
    cat = load_catalog()
    origin_x = origin_y = 0.0
    if polys:
        polys.sort(reverse=True)
        _, w, d, _pts, origin_x, origin_y = polys[0]
        room = Room(name="CAD房间", kind="客厅", width=round(w, 3), depth=round(d, 3), height=2.8, source="CAD图纸")
    else:
        xs, ys = [], []
        for e in msp.query("LINE"):
            xs += [float(e.dxf.start.x) * scale, float(e.dxf.end.x) * scale]
            ys += [float(e.dxf.start.y) * scale, float(e.dxf.end.y) * scale]
        if xs:
            origin_x, origin_y = min(xs), min(ys)
            w, d = max(xs) - origin_x, max(ys) - origin_y
            room = Room(name="CAD范围", kind="客厅", width=max(2.0, round(w, 3)), depth=max(2.0, round(d, 3)), height=2.8, source="CAD图纸")
        else:
            room = Room(source="CAD图纸")
    room.openings = _doors_from_dxf_lines(msp, scale, origin_x, origin_y, room.width, room.depth)
    return {
        "room": room,
        "task": "floor",
        "floor_tile": cat["tile_floors"][0],
        "wall_tile": cat["tile_walls"][0],
        "ceiling": cat["ceilings"][0],
        "pattern": "straight",
        "cad_rooms": len(polys),
        "text": "",
    }
