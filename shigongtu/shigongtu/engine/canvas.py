from __future__ import annotations

import html
import math
from dataclasses import dataclass, field
from typing import Any

A3_W = 420.0
A3_H = 297.0

LAYER_COLOR = {
    "S-AXIS": "#cc0000",
    "S-WALL": "#111111",
    "S-COL": "#003399",
    "S-DOOR": "#007777",
    "S-WIND": "#007777",
    "S-DIM": "#007700",
    "S-TEXT": "#114422",
    "S-FURN": "#886600",
    "S-HATCH": "#999999",
    "S-TITLE": "#111111",
    "S-PLUMB-W": "#0055aa",
    "S-PLUMB-D": "#880088",
    "S-ELEC": "#aa7700",
    "S-HVAC": "#006688",
    "S-VENT": "#227722",
    "S-FIRE": "#bb0000",
    "S-STRUCT": "#003366",
    "S-SITE": "#335533",
}

ROOM_FILL = {
    "楼梯": "#fde68a",
    "电梯": "#fcd34d",
    "电梯厅": "#fef3c7",
    "卫生间": "#a5f3fc",
    "走廊": "#f3f4f6",
    "门厅": "#e0e7ff",
    "办公": "#dbeafe",
    "卧室": "#fce7f3",
    "客厅": "#ede9fe",
    "厨房": "#ffedd5",
    "阳台": "#e0f2fe",
    "车间": "#e5e7eb",
    "教室": "#d1fae5",
    "设备": "#fecaca",
    "竖井": "#d4d4d8",
    "商铺": "#fef9c3",
    "营业": "#ddd6fe",
    "病房": "#bbf7d0",
    "客房": "#fbcfe8",
    "车库": "#e2e8f0",
    "人防": "#fed7aa",
}

DXF_ACI = {
    "S-AXIS": 1,
    "S-WALL": 7,
    "S-COL": 5,
    "S-DOOR": 4,
    "S-WIND": 4,
    "S-DIM": 3,
    "S-TEXT": 3,
    "S-FURN": 2,
    "S-HATCH": 8,
    "S-TITLE": 7,
    "S-PLUMB-W": 5,
    "S-PLUMB-D": 6,
    "S-ELEC": 2,
    "S-HVAC": 4,
    "S-VENT": 3,
    "S-FIRE": 1,
    "S-STRUCT": 5,
    "S-SITE": 3,
}


def _esc(t: str) -> str:
    return html.escape(t, quote=True)


@dataclass
class Drawing:
    number: str
    name: str
    discipline: str
    spec_name: str
    scale: int = 100
    location: str = ""
    designer: str = ""
    paper: str = "A3"
    ops: list[dict[str, Any]] = field(default_factory=list)
    origin_x: float = 40.0
    origin_y: float = 230.0
    notes: list[str] = field(default_factory=list)
    legend: list[tuple[str, str]] = field(default_factory=list)

    def m2p(self, x: float, y: float) -> tuple[float, float]:
        k = 1000.0 / self.scale
        return self.origin_x + x * k, self.origin_y - y * k

    def fit_plan(
        self,
        xmin: float,
        ymin: float,
        xmax: float,
        ymax: float,
        box: tuple[float, float, float, float] | None = None,
    ) -> None:
        left, top, right, bot = box or (32.0, 14.0, 408.0, 238.0)
        pad = 14.0
        avail_w = right - left - pad * 2
        avail_h = bot - top - pad * 2
        mw = max(0.5, xmax - xmin) * 1000
        mh = max(0.5, ymax - ymin) * 1000
        chosen = 2000
        for s in (50, 75, 100, 150, 200, 250, 300, 400, 500, 800, 1000, 2000):
            if mw / s <= avail_w and mh / s <= avail_h:
                chosen = s
                break
        self.scale = chosen
        k = 1000.0 / chosen
        dw, dh = (xmax - xmin) * k, (ymax - ymin) * k
        self.origin_x = left + pad + (avail_w - dw) / 2 - xmin * k
        self.origin_y = top + pad + (avail_h - dh) / 2 + ymax * k

    def add(self, **kw: Any) -> None:
        self.ops.append(kw)

    def line(self, x1: float, y1: float, x2: float, y2: float, layer: str = "S-WALL", lw: float = 0.25, lt: str = "solid") -> None:
        self.add(t="line", x1=x1, y1=y1, x2=x2, y2=y2, layer=layer, lw=lw, lt=lt, model=True)

    def pline(self, pts: list[tuple[float, float]], layer: str = "S-WALL", lw: float = 0.25, close: bool = False, fill: str = "none") -> None:
        self.add(t="pline", pts=pts, layer=layer, lw=lw, close=close, fill=fill, model=True)

    def rect(self, x: float, y: float, w: float, h: float, layer: str = "S-WALL", lw: float = 0.2, fill: str = "none") -> None:
        self.pline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], layer=layer, lw=lw, close=True, fill=fill)

    def circle(self, x: float, y: float, r: float, layer: str = "S-TEXT", lw: float = 0.2, fill: str = "none") -> None:
        self.add(t="circle", x=x, y=y, r=r, layer=layer, lw=lw, fill=fill, model=True)

    def text(self, x: float, y: float, s: str, layer: str = "S-TEXT", h: float = 2.5, anchor: str = "m") -> None:
        self.add(t="text", x=x, y=y, s=s, layer=layer, h=h, anchor=anchor, model=True)

    def paper_line(self, x1: float, y1: float, x2: float, y2: float, layer: str = "S-TITLE", lw: float = 0.3) -> None:
        self.add(t="line", x1=x1, y1=y1, x2=x2, y2=y2, layer=layer, lw=lw, lt="solid", model=False)

    def paper_rect(self, x: float, y: float, w: float, h: float, layer: str = "S-TITLE", lw: float = 0.3, fill: str = "none") -> None:
        pts = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        self.add(t="pline", pts=pts, layer=layer, lw=lw, close=True, fill=fill, model=False)

    def paper_text(self, x: float, y: float, s: str, h: float = 3.0, anchor: str = "m", layer: str = "S-TITLE") -> None:
        self.add(t="text", x=x, y=y, s=s, layer=layer, h=h, anchor=anchor, model=False)

    def dim_h(self, x1: float, x2: float, y: float, offset: float = -1.2) -> None:
        yy = y + offset
        self.line(x1, y, x1, yy - 0.3, "S-DIM", 0.13)
        self.line(x2, y, x2, yy - 0.3, "S-DIM", 0.13)
        self.line(x1, yy, x2, yy, "S-DIM", 0.18)
        self.text((x1 + x2) / 2, yy + (0.35 if offset < 0 else -0.35), _mm(abs(x2 - x1)), "S-DIM", 2.0)

    def dim_v(self, y1: float, y2: float, x: float, offset: float = -1.2) -> None:
        xx = x + offset
        self.line(x, y1, xx - 0.3, y1, "S-DIM", 0.13)
        self.line(x, y2, xx - 0.3, y2, "S-DIM", 0.13)
        self.line(xx, y1, xx, y2, "S-DIM", 0.18)
        self.text(xx + (0.15 if offset < 0 else -0.15), (y1 + y2) / 2, _mm(abs(y2 - y1)), "S-DIM", 2.0, "m")

    def to_svg(self) -> str:
        parts = [
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{A3_W}mm" height="{A3_H}mm" viewBox="0 0 {A3_W} {A3_H}">',
            "<style>text{font-family:'Microsoft YaHei','Noto Sans SC','WenQuanYi Micro Hei',SimSun,sans-serif;}</style>",
            f'<rect x="0" y="0" width="{A3_W}" height="{A3_H}" fill="#f7f4ea"/>',
        ]
        _title_block(self)
        for op in self.ops:
            parts.append(_svg_op(self, op))
        parts.append("</svg>")
        return "\n".join(parts)

    def to_dxf(self, doc: Any) -> None:
        msp = doc.modelspace()
        for name, aci in DXF_ACI.items():
            if name not in doc.layers:
                lt = "CENTER" if name == "S-AXIS" else "Continuous"
                try:
                    doc.layers.add(name, color=aci, linetype=lt)
                except Exception:
                    doc.layers.add(name, color=aci)
        k = 1000.0  # m -> mm in model
        for op in self.ops:
            if not op.get("model", True):
                continue
            layer = op.get("layer", "S-WALL")
            t = op["t"]
            if t == "line":
                msp.add_line((op["x1"] * k, op["y1"] * k), (op["x2"] * k, op["y2"] * k), dxfattribs={"layer": layer})
            elif t == "pline":
                pts = [(p[0] * k, p[1] * k) for p in op["pts"]]
                if op.get("close") and pts and pts[0] != pts[-1]:
                    pts = pts + [pts[0]]
                msp.add_lwpolyline(pts, dxfattribs={"layer": layer})
            elif t == "circle":
                msp.add_circle((op["x"] * k, op["y"] * k), op["r"] * k, dxfattribs={"layer": layer})
            elif t == "text":
                h = max(200.0, op.get("h", 2.5) * self.scale)
                msp.add_text(
                    op["s"],
                    dxfattribs={"layer": layer, "height": h * 0.8},
                ).set_placement((op["x"] * k, op["y"] * k))


def _mm(v: float) -> str:
    n = abs(v) * 1000
    if abs(n - round(n)) < 0.6:
        return str(int(round(n)))
    return f"{n:.0f}"


def _svg_dash(lt: str) -> str:
    if lt == "center":
        return 'stroke-dasharray="8 2 1.5 2"'
    if lt == "dash":
        return 'stroke-dasharray="4 2"'
    if lt == "dot":
        return 'stroke-dasharray="1 1.5"'
    return ""


def _xy(d: Drawing, op: dict[str, Any], x: float, y: float) -> tuple[float, float]:
    if op.get("model", True):
        return d.m2p(x, y)
    return x, y


def _svg_op(d: Drawing, op: dict[str, Any]) -> str:
    layer = op.get("layer", "S-WALL")
    color = LAYER_COLOR.get(layer, "#222")
    lw = op.get("lw", 0.25)
    t = op["t"]
    if t == "line":
        x1, y1 = _xy(d, op, op["x1"], op["y1"])
        x2, y2 = _xy(d, op, op["x2"], op["y2"])
        dash = _svg_dash(op.get("lt", "solid"))
        return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="{lw}" {dash} fill="none"/>'
    if t == "pline":
        pts = []
        for px, py in op["pts"]:
            x, y = _xy(d, op, px, py)
            pts.append(f"{x:.2f},{y:.2f}")
        fill = op.get("fill") or "none"
        close = " Z" if op.get("close") else ""
        return f'<path d="M{" L".join(pts)}{close}" stroke="{color}" stroke-width="{lw}" fill="{fill}"/>'
    if t == "circle":
        x, y = _xy(d, op, op["x"], op["y"])
        if op.get("model", True):
            r = op["r"] * 1000 / d.scale
        else:
            r = op["r"]
        fill = op.get("fill") or "none"
        return f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{r:.2f}" stroke="{color}" stroke-width="{lw}" fill="{fill}"/>'
    if t == "text":
        x, y = _xy(d, op, op["x"], op["y"])
        h = op.get("h", 2.5)
        anchor = {"m": "middle", "s": "start", "e": "end"}.get(op.get("anchor", "m"), "middle")
        return (
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="{h}" fill="{color}" text-anchor="{anchor}" '
            f'dominant-baseline="middle">{_esc(str(op["s"]))}</text>'
        )
    return ""


def _title_block(d: Drawing) -> None:
    d.paper_rect(10, 10, 400, 277, "S-TITLE", 0.7)
    d.paper_rect(25, 10, 385, 277, "S-TITLE", 0.35)
    # title
    x, y, w, h = 230, 247, 180, 40
    d.paper_rect(x, y, w, h, "S-TITLE", 0.4)
    cols = [0, 70, 120, 180]
    rows = [0, 14, 27, 40]
    for c in cols:
        d.paper_line(x + c, y, x + c, y + h)
    for r in rows:
        d.paper_line(x, y + r, x + w, y + r)
    d.paper_text(x + 35, y + 7, d.spec_name[:16], 3.2)
    d.paper_text(x + 35, y + 20, d.name, 3.6)
    d.paper_text(x + 95, y + 7, f"图号 {d.number}", 2.6)
    d.paper_text(x + 95, y + 20, f"比例 1:{d.scale}", 2.6)
    d.paper_text(x + 150, y + 7, d.discipline, 2.6)
    d.paper_text(x + 150, y + 20, d.paper, 2.6)
    d.paper_text(x + 35, y + 33.5, f"设计 {d.designer or '—'}    {d.location}", 2.2)
    d.paper_text(x + 150, y + 33.5, "会签栏 示意", 2.0)
    d.paper_text(32, 18, "自动生成 · 示意深度 · 须专业负责人审核", 2.2, "s", "S-DIM")


def wrap_cn(text: str, n: int) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        buf = ""
        for ch in para:
            buf += ch
            if len(buf) >= n:
                lines.append(buf)
                buf = ""
        lines.append(buf if buf else ("" if not para else buf))
    return [ln for ln in lines if ln is not None]


def north_arrow(d: Drawing, x: float, y: float) -> None:
    d.add(t="pline", pts=[(x, y + 8), (x - 3, y - 4), (x, y - 1), (x + 3, y - 4)], layer="S-TITLE", lw=0.3, close=True, fill="#111", model=False)
    d.paper_text(x, y + 11, "N", 3.2)


def scale_bar(d: Drawing, x: float, y: float) -> None:
    d.paper_text(x, y - 4, f"1:{d.scale}", 2.2, "s")
    d.paper_line(x, y, x + 40, y, "S-TITLE", 0.4)
    for i in range(5):
        d.paper_line(x + i * 10, y - 1.5, x + i * 10, y + 1.5, "S-TITLE", 0.25)
    d.paper_text(x, y + 4, "0", 2.0)
    meters = 40 * d.scale / 1000
    d.paper_text(x + 40, y + 4, f"{meters:g}m", 2.0)


def new_sheet(number: str, name: str, discipline: str, model) -> Drawing:
    s = model.spec
    return Drawing(
        number=number,
        name=name,
        discipline=discipline,
        spec_name=s.name,
        location=s.location,
        designer=s.designer,
    )
