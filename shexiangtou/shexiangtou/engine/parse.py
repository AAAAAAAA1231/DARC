from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from typing import Any

from shexiangtou.config import RESOURCES


def load_catalog() -> dict[str, Any]:
    return json.loads((RESOURCES / "catalog.json").read_text(encoding="utf-8"))


@dataclass
class Door:
    x: float
    y: float
    heading: float  # radians, inward
    width: float = 1.0


@dataclass
class Scene:
    name: str = "办公室"
    width: float = 12.0
    depth: float = 8.0
    height: float = 3.0
    source: str = "手动"
    purpose: str = ""
    indoor: bool = True
    doors: list[Door] = field(default_factory=list)

    @property
    def width_m(self) -> float:
        return self.width

    @property
    def depth_m(self) -> float:
        return self.depth

    @property
    def height_m(self) -> float:
        return self.height

    @property
    def space_type(self) -> str:
        return self.name


_DIM = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mm|毫米|m|米)?\s*[xX×*乘]+\s*(\d+(?:\.\d+)?)\s*(mm|毫米|m|米)?",
    re.I,
)
_H = re.compile(r"(层高|净高|吊高)\s*(\d+(?:\.\d+)?)\s*(m|米|mm)?")
_DOORS = re.compile(r"(\d+)\s*(个|扇)?\s*(门|出入口|门口)")
_SPACE = re.compile(
    r"(办公室|会议室|走廊|门厅|大堂|出入口|电梯|商铺|收银|教室|仓库|车间|停车场|车库|周界|室外)"
)


def _m(v: float, u: str | None) -> float:
    u = (u or "").lower()
    if u in ("mm", "毫米") or (not u and v >= 50):
        return v / 1000
    return v


def parse_description(text: str) -> Scene:
    cat = load_catalog()
    names = [s["id"] for s in cat["spaces"]]
    t = text or ""
    name = "办公室"
    hits = [n for n in names if n and n in t]
    if hits:
        name = max(hits, key=len)
    m = _SPACE.search(t)
    if m:
        mapping = {
            "办公室": "办公室",
            "会议室": "会议室",
            "走廊": "走廊",
            "门厅": "门厅/大堂",
            "大堂": "门厅/大堂",
            "出入口": "出入口",
            "电梯": "电梯厅",
            "商铺": "商铺/收银",
            "收银": "商铺/收银",
            "教室": "教室",
            "仓库": "仓库",
            "车间": "仓库",
            "停车场": "停车场",
            "车库": "停车场",
            "周界": "周界",
            "室外": "室外场地",
        }
        name = mapping.get(m.group(1), name)
    width, depth, height = 12.0, 8.0, 3.0
    dims = list(_DIM.findall(t))
    if dims:
        a, ua, b, ub = dims[0]
        width, depth = _m(float(a), ua), _m(float(b), ub)
        if width < 0.5:
            width *= 1000
        if depth < 0.5:
            depth *= 1000
    hm = _H.search(t)
    if hm:
        height = _m(float(hm.group(2)), hm.group(3))
        if height < 1.5:
            height = 3.0
    spec = next((s for s in cat["spaces"] if s["id"] == name), cat["spaces"][0])
    nd = 1
    dm = _DOORS.search(t)
    if dm:
        nd = max(1, int(dm.group(1)))
    if "无门" in t:
        nd = 0
    doors = _default_doors(width, depth, nd)
    purpose = ""
    if "人脸" in t or "辨认" in t:
        purpose = "辨认"
    elif "识别" in t:
        purpose = "识别"
    elif "监视" in t or "周界" in t:
        purpose = "监视"
    return Scene(
        name=spec["id"],
        width=width,
        depth=depth,
        height=height,
        source="语言描述",
        purpose=purpose,
        indoor=bool(spec["indoor"]),
        doors=doors,
    )


def _default_doors(width: float, depth: float, n: int) -> list[Door]:
    if n <= 0:
        return []
    corridor = min(width, depth) <= 3.5 and max(width, depth) >= 8
    doors: list[Door] = []
    if corridor and width >= depth:
        doors.append(Door(x=0.05, y=depth / 2, heading=0.0, width=1.0))
        if n >= 2:
            doors.append(Door(x=width - 0.05, y=depth / 2, heading=math.pi, width=1.0))
    elif corridor:
        doors.append(Door(x=width / 2, y=0.05, heading=math.pi / 2, width=1.0))
        if n >= 2:
            doors.append(Door(x=width / 2, y=depth - 0.05, heading=-math.pi / 2, width=1.0))
    else:
        doors.append(Door(x=width / 2, y=0.05, heading=math.pi / 2, width=1.0))
        if n >= 2:
            doors.append(Door(x=width / 2, y=depth - 0.05, heading=-math.pi / 2, width=1.0))
    if n >= 3:
        doors.append(Door(x=0.05, y=depth / 2, heading=0.0, width=1.0))
    if n >= 4:
        doors.append(Door(x=width - 0.05, y=depth / 2, heading=math.pi, width=1.0))
    # unique
    uniq: list[Door] = []
    for d in doors:
        if any(math.hypot(d.x - u.x, d.y - u.y) < 0.6 for u in uniq):
            continue
        uniq.append(d)
    return uniq[:n]


def parse_pdf_bytes(data: bytes) -> Scene:
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    scene = parse_description(text or "办公室 12x8")
    scene.source = "PDF图纸"
    return scene


def parse_dxf_bytes(data: bytes) -> Scene:
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
    scale = {0: 0.001, 1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}.get(ins, 0.001)
    polys: list[tuple[float, float, float, list[tuple[float, float]]]] = []
    for e in msp:
        try:
            t = e.dxftype()
        except Exception:
            continue
        pts: list[tuple[float, float]] = []
        if t == "LWPOLYLINE" and bool(e.closed):
            pts = [(float(p[0]) * scale, float(p[1]) * scale) for p in e.get_points("xy")]
        elif t == "POLYLINE" and bool(getattr(e, "is_closed", False)):
            pts = [(float(v.dxf.location.x) * scale, float(v.dxf.location.y) * scale) for v in e.vertices]
        if len(pts) >= 3:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            w, d = max(xs) - min(xs), max(ys) - min(ys)
            if w > 1.0 and d > 1.0:
                minx, miny = min(xs), min(ys)
                local = [(p[0] - minx, p[1] - miny) for p in pts]
                polys.append((w * d, w, d, local))
    texts: list[str] = []
    for e in msp.query("TEXT MTEXT"):
        try:
            texts.append(str(e.dxf.text if e.dxftype() == "TEXT" else e.text))
        except Exception:
            pass
    scene = parse_description(" ".join(texts) + " 办公室")
    origin = (0.0, 0.0)
    if polys:
        polys.sort(reverse=True)
        _, w, d, local = polys[0]
        scene.width, scene.depth = round(w, 3), round(d, 3)
        xs = [p[0] for p in local]
        ys = [p[1] for p in local]
        origin = (min(xs), min(ys))
        # shift local already min-based
    if scene.width > 50 or scene.depth > 50:
        scene.width = round(scene.width / 1000, 3)
        scene.depth = round(scene.depth / 1000, 3)
        scale *= 0.001
    doors = _doors_from_dxf(msp, scale, scene.width, scene.depth)
    if doors:
        scene.doors = doors
    else:
        scene.doors = _default_doors(scene.width, scene.depth, 1)
    scene.source = "CAD图纸"
    return scene


def _doors_from_dxf(msp, scale: float, width: float, depth: float) -> list[Door]:
    doors: list[Door] = []
    cx, cy = width / 2, depth / 2
    for e in msp.query("LINE"):
        x1, y1 = float(e.dxf.start.x) * scale, float(e.dxf.start.y) * scale
        x2, y2 = float(e.dxf.end.x) * scale, float(e.dxf.end.y) * scale
        length = math.hypot(x2 - x1, y2 - y1)
        if length < 0.7 or length > 2.6:
            continue
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        # keep doors near room bbox
        if mx < -0.5 or my < -0.5 or mx > width + 0.5 or my > depth + 0.5:
            continue
        heading = math.atan2(cy - my, cx - mx)
        doors.append(
            Door(
                x=min(max(mx, 0.05), width - 0.05),
                y=min(max(my, 0.05), depth - 0.05),
                heading=heading,
                width=round(length, 2),
            )
        )
    # unique by proximity
    uniq: list[Door] = []
    for d in doors:
        if any(math.hypot(d.x - u.x, d.y - u.y) < 0.8 for u in uniq):
            continue
        uniq.append(d)
    return uniq[:8]
