from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from dengju.config import RESOURCES


def load_catalog() -> dict[str, Any]:
    return json.loads((RESOURCES / "catalog.json").read_text(encoding="utf-8"))


@dataclass
class RoomInput:
    name: str = "普通办公室"
    width: float = 7.2
    depth: float = 9.0
    height: float = 2.8
    source: str = "手动"
    E: float = 0
    work_h: float = 0.75
    mf: float = 0.8
    cct: int = 4000
    ra_min: int = 80

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
    def illuminance_lx(self) -> float:
        return self.E

    @property
    def room_type(self) -> str:
        return self.name


_DIM = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mm|毫米|m|米)?\s*[xX×*乘]+\s*(\d+(?:\.\d+)?)\s*(mm|毫米|m|米)?",
    re.I,
)
_H = re.compile(r"(层高|净高|吊高)\s*(\d+(?:\.\d+)?)\s*(m|米|mm)?")
_E = re.compile(r"(\d{2,4})\s*(lx|勒克斯|勒)")
_ROOM = re.compile(
    r"(办公室|会议室|教室|走廊|门厅|大堂|商场|病房|厂房|车间|起居室|客厅|卧室|厨房|卫生间|车库|停车场)"
)


def _m(v: float, u: str | None) -> float:
    u = (u or "").lower()
    if u in ("mm", "毫米") or (not u and v >= 50):
        return v / 1000
    return v


def parse_description(text: str) -> RoomInput:
    cat = load_catalog()
    names = [r["name"] for r in cat["rooms"]]
    name = "普通办公室"
    t = text or ""
    hits = [n for n in names if n and n in t]
    if hits:
        name = max(hits, key=len)
    m = _ROOM.search(t)
    if m:
        w = m.group(1)
        mapping = {
            "办公室": "普通办公室",
            "会议室": "会议室",
            "教室": "普通教室",
            "走廊": "走廊",
            "门厅": "门厅/大堂",
            "大堂": "门厅/大堂",
            "商场": "商场营业厅",
            "病房": "病房",
            "厂房": "工业一般加工",
            "车间": "工业一般加工",
            "起居室": "住宅起居室",
            "客厅": "住宅起居室",
            "卧室": "住宅卧室",
            "厨房": "住宅厨房",
            "卫生间": "卫生间",
            "车库": "车库/停车场",
            "停车场": "车库/停车场",
        }
        name = mapping.get(w, name)
        if "精细" in t or "高档" in t or "设计" in t:
            if "办公" in t:
                name = "高档办公室/设计"
            if "工业" in t or "车间" in t:
                name = "工业精细加工"
    width, depth, height = 7.2, 9.0, 2.8
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
            height = 2.8
    spec = next(r for r in cat["rooms"] if r["name"] == name)
    E = spec["E"]
    em = _E.search(t)
    if em:
        E = float(em.group(1))
    return RoomInput(
        name=name, width=width, depth=depth, height=height, source="语言描述",
        E=E, work_h=spec["work_h"], mf=spec["mf"],
    )


def parse_pdf_bytes(data: bytes) -> RoomInput:
    import io
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    r = parse_description(text or "办公室 7.2x9.0 300lx")
    r.source = "PDF图纸"
    return r


def parse_dxf_bytes(data: bytes) -> RoomInput:
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
    polys = []
    for e in msp:
        try:
            t = e.dxftype()
        except Exception:
            continue
        pts = []
        if t == "LWPOLYLINE" and bool(e.closed):
            pts = [(float(p[0]) * scale, float(p[1]) * scale) for p in e.get_points("xy")]
        elif t == "POLYLINE" and bool(getattr(e, "is_closed", False)):
            pts = [(float(v.dxf.location.x) * scale, float(v.dxf.location.y) * scale) for v in e.vertices]
        if len(pts) >= 3:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            w, d = max(xs) - min(xs), max(ys) - min(ys)
            if w > 1.0 and d > 1.0:
                polys.append((w * d, w, d))
    texts = []
    for e in msp.query("TEXT MTEXT"):
        try:
            texts.append(str(e.dxf.text if e.dxftype() == "TEXT" else e.text))
        except Exception:
            pass
    r = parse_description(" ".join(texts) + " 办公室")
    if polys:
        polys.sort(reverse=True)
        _, w, d = polys[0]
        r.width, r.depth = round(w, 3), round(d, 3)
    else:
        xs, ys = [], []
        for e in msp.query("LINE"):
            xs += [float(e.dxf.start.x) * scale, float(e.dxf.end.x) * scale]
            ys += [float(e.dxf.start.y) * scale, float(e.dxf.end.y) * scale]
        if xs:
            r.width = round(max(xs) - min(xs), 3)
            r.depth = round(max(ys) - min(ys), 3)
    if r.width > 50 or r.depth > 50:
        r.width = round(r.width / 1000, 3)
        r.depth = round(r.depth / 1000, 3)
    r.source = "CAD图纸"
    return r
