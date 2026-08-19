from __future__ import annotations

import html
from typing import Any


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


class PlanSvg:
    def __init__(self, room_w: float, room_d: float, title: str, pad: float = 40):
        self.W, self.D, self.title = room_w, room_d, title
        self.pad = pad
        self.scale = (860 - 2 * pad) / max(room_w, 0.5)
        self.parts: list[str] = []

    def px(self, x: float, y: float) -> tuple[float, float]:
        return self.pad + x * self.scale, self.pad + (self.D - y) * self.scale

    def rect(self, x, y, w, h, fill="#fff", stroke="#222", sw=1, opacity=1, dash=""):
        x0, y0 = self.px(x, y + h)
        ds = f'stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(
            f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{w*self.scale:.1f}" height="{h*self.scale:.1f}" '
            f'fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" stroke-width="{sw}" {ds}/>'
        )

    def line(self, x1, y1, x2, y2, stroke="#c00", sw=1, dash=""):
        a = self.px(x1, y1)
        b = self.px(x2, y2)
        ds = f'stroke-dasharray="{dash}"' if dash else ""
        self.parts.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" stroke="{stroke}" stroke-width="{sw}" {ds}/>')

    def circle(self, x, y, r, fill="#facc15", stroke="#222"):
        cx, cy = self.px(x, y)
        self.parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r*self.scale:.1f}" fill="{fill}" stroke="{stroke}"/>')

    def text(self, x, y, s, size=12, fill="#1c2a3a", anchor="middle"):
        cx, cy = self.px(x, y)
        self.parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
            f'dominant-baseline="middle" font-family="Microsoft YaHei, Noto Sans SC, sans-serif">{_esc(s)}</text>'
        )

    def finish(self, extra: str = "") -> str:
        bw = self.pad * 2 + self.W * self.scale
        bh = self.pad * 2 + self.D * self.scale + 36
        body = "".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw:.0f}" height="{bh:.0f}" viewBox="0 0 {bw:.0f} {bh:.0f}">'
            f'<rect width="100%" height="100%" fill="#f7f4ea"/>'
            f'<text x="{bw/2:.0f}" y="22" text-anchor="middle" font-size="16" fill="#1b4f8a" '
            f'font-family="Microsoft YaHei, sans-serif">{_esc(self.title)}</text>'
            f"{body}{extra}</svg>"
        )


def svg_floor(room, layout: dict[str, Any]) -> str:
    p = PlanSvg(room.width, room.depth, f"{room.name} 地砖排版  {layout['tile_w']*1000:.0f}×{layout['tile_h']*1000:.0f}  {layout['note']}")
    p.rect(0, 0, room.width, room.depth, fill="#efe7d6", stroke="#111", sw=2)
    for t in layout["tiles"]:
        fill = "#e8eef6" if t["full"] else "#fed7aa"
        p.rect(t["x"], t["y"], t["w"], t["h"], fill=fill, stroke="#3b5b7a", sw=0.8)
    p.text(room.width / 2, -0.15, f"{room.width:.2f}m", 11)
    # dim on left - skip negative, put inside
    p.text(0.15, room.depth / 2, f"{room.depth:.2f}m", 11, anchor="start")
    return p.finish()


def svg_walls(room, walls: list[dict[str, Any]]) -> str:
    # unfold 4 walls in a row conceptually - draw as 4 stacked elevations in one svg via multiple plan strips
    total_h = sum(w["wall_h"] + 0.4 for w in walls)
    max_l = max(w["wall_len"] for w in walls)
    # use a fake "room" canvas: width=max_l, depth=total_h
    p = PlanSvg(max_l, total_h, f"{room.name} 墙砖展开排版")
    y0 = 0.0
    for w in walls:
        p.text(0.05, y0 + w["wall_h"] + 0.15, w["name"], 11, anchor="start")
        p.rect(0, y0, w["wall_len"], w["wall_h"], fill="#f3f4f6", stroke="#111", sw=1.5)
        for t in w["tiles"]:
            fill = "#dbeafe" if t["full"] else "#fecaca"
            p.rect(t["x"], y0 + t["y"], t["w"], t["h"], fill=fill, stroke="#1e3a5f", sw=0.6)
        for h in w.get("holes") or []:
            p.rect(h["x"], y0 + h["y"], h["w"], h["h"], fill="#f7f4ea", stroke="#b91c1c", sw=1.5, dash="4 3")
        y0 += w["wall_h"] + 0.4
    return p.finish()


def svg_ceiling(room, ceil: dict[str, Any]) -> str:
    p = PlanSvg(room.width, room.depth, f"{room.name} 吊顶排版  {ceil['kind']}  主龙骨@{ceil['main_spacing']}m")
    p.rect(0, 0, room.width, room.depth, fill="#f8fafc", stroke="#111", sw=2)
    for pan in ceil["panels"]:
        fill = "#e2e8f0" if pan["cut"] else "#fff"
        p.rect(pan["x"], pan["y"], pan["w"], pan["h"], fill=fill, stroke="#64748b", sw=0.7)
    for m in ceil["mains"]:
        p.line(m["x1"], m["y1"], m["x2"], m["y2"], stroke="#b45309", sw=2)
    for s in ceil["seconds"]:
        p.line(s["x1"], s["y1"], s["x2"], s["y2"], stroke="#0369a1", sw=1, dash="6 4")
    for h in ceil["hangers"]:
        p.circle(h["x"], h["y"], 0.06, fill="#111")
    for L in ceil["lights"]:
        p.circle(L["x"], L["y"], 0.12, fill="#fde68a")
    ht = ceil["hatch"]
    p.rect(ht["x"], ht["y"], ht["w"], ht["h"], fill="none", stroke="#dc2626", sw=1.5, dash="5 3")
    p.text(ht["x"] + ht["w"] / 2, ht["y"] + ht["h"] / 2, "检修口", 10, fill="#dc2626")
    return p.finish()


def svg_furniture(room, furn: dict[str, Any]) -> str:
    p = PlanSvg(room.width, room.depth, f"{room.name} 家具布置  {furn['kind']}")
    p.rect(0, 0, room.width, room.depth, fill="#f5f0e6", stroke="#111", sw=2)
    colors = ["#93c5fd", "#f9a8d4", "#fcd34d", "#86efac", "#c4b5fd", "#fda4af"]
    for i, it in enumerate(furn["items"]):
        p.rect(it["x"], it["y"], it["w"], it["d"], fill=colors[i % len(colors)], stroke="#1e3a5f", sw=1, opacity=0.9)
        p.text(it["x"] + it["w"] / 2, it["y"] + it["d"] / 2, it["name"], 11)
    for o in room.openings:
        if o.wall == "S":
            p.rect(o.offset, 0, o.width, 0.08, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(o.offset + o.width / 2, 0.25, "门", 10, fill="#b91c1c")
    return p.finish()
