from __future__ import annotations

import html
from typing import Any


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


class PlanSvg:
    def __init__(self, room_w: float, room_d: float, title: str, pad: float = 40):
        self.W, self.D, self.title = room_w, room_d, title
        self.pad = pad
        self.scale = (860 - 2 * pad) / max(room_w, room_d, 0.5)
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
        fill = "#fca5a5" if t.get("sleeve") else ("#e8eef6" if t["full"] else "#fed7aa")
        p.rect(t["x"], t["y"], t["w"], t["h"], fill=fill, stroke="#3b5b7a", sw=0.8)
    wet = layout.get("wet_features") or {}
    doors = [o for o in getattr(room, "openings", []) or [] if getattr(o, "kind", "door") == "door"]
    main_door = max(doors, key=lambda o: float(getattr(o, "width", 0))) if doors else None
    door_wall = layout.get("door_wall") or (getattr(main_door, "wall", "S") if main_door else "S")
    cx = wet.get("cross_x")
    if cx is None and main_door:
        if door_wall in ("S", "N"):
            cx = main_door.offset + main_door.width / 2
        elif door_wall == "W":
            cx = 0.12
        else:
            cx = room.width - 0.12
    if cx is None:
        cx = room.width / 2
    cy = wet.get("cross_y")
    if cy is None:
        cy = room.depth / 2
    p.line(cx, 0, cx, room.depth, stroke="#b45309", sw=1, dash="6 4")
    p.line(0, cy, room.width, cy, stroke="#b45309", sw=1, dash="6 4")
    p.text(cx + 0.12, cy + 0.12, "十字控制线", 10, fill="#92400e", anchor="start")
    ramp = wet.get("ramp")
    if ramp:
        p.rect(ramp["x"], ramp["y"], ramp["w"], ramp.get("d") or 0.3, fill="#fde68a", stroke="#b45309", sw=1.2, opacity=0.85)
        p.text(ramp["x"] + ramp["w"] / 2, ramp["y"] + (ramp.get("d") or 0.3) / 2, "斜坡≤15mm", 10, fill="#92400e")
    drain = wet.get("drain")
    if drain:
        p.circle(drain["x"], drain["y"], 0.08, fill="#0ea5e9", stroke="#0c4a6e")
        p.text(drain["x"] + 0.22, drain["y"], "地漏套割 1％", 11, fill="#0c4a6e", anchor="start")
        for tx, ty in ((0.25, 0.25), (room.width - 0.25, 0.25), (0.25, room.depth - 0.25), (room.width - 0.25, room.depth - 0.25)):
            p.line(tx, ty, drain["x"], drain["y"], stroke="#38bdf8", sw=0.8, dash="4 3")
    for o in getattr(room, "openings", []) or []:
        if getattr(o, "kind", "door") != "door":
            continue
        label = "门口整砖" if o.wall == door_wall and layout.get("pattern") != "laminate" else "门"
        if layout.get("pattern") == "laminate" and o.wall == door_wall:
            label = "门口起铺"
        if o.wall == "S":
            p.rect(o.offset, 0, o.width, 0.06, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(o.offset + o.width / 2, 0.18, label, 10, fill="#b91c1c")
        elif o.wall == "N":
            p.rect(o.offset, room.depth - 0.06, o.width, 0.06, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(o.offset + o.width / 2, room.depth - 0.18, label, 10, fill="#b91c1c")
        elif o.wall == "W":
            p.rect(0, o.offset, 0.06, o.width, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(0.22, o.offset + o.width / 2, label, 10, fill="#b91c1c", anchor="start")
        elif o.wall == "E":
            p.rect(room.width - 0.06, o.offset, 0.06, o.width, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(room.width - 0.22, o.offset + o.width / 2, label, 10, fill="#b91c1c")
    p.text(room.width / 2, -0.15, f"{room.width:.2f}m", 11)
    p.text(0.15, room.depth / 2, f"{room.depth:.2f}m", 11, anchor="start")
    return p.finish()


def svg_walls(room, walls: list[dict[str, Any]]) -> str:
    """Four elevations in a 2×2 grid so 墙砖/吊顶一样，打开就能看见，不用往下翻。"""
    walls = list(walls or [])[:4]
    while len(walls) < 4:
        walls.append({"name": "墙", "wall_len": 1, "wall_h": 1, "tiles": [], "holes": []})
    pad, gap, title_h, label_h = 18, 20, 32, 22
    cell_w, cell_h = 500, 310
    cols, rows = 2, 2
    bw = pad * 2 + cols * cell_w + gap
    bh = title_h + pad * 2 + rows * (cell_h + label_h) + gap + 28
    parts: list[str] = [
        f'<rect width="100%" height="100%" fill="#f7f4ea"/>',
        f'<text x="{bw/2:.0f}" y="22" text-anchor="middle" font-size="16" fill="#1b4f8a" '
        f'font-family="Microsoft YaHei, sans-serif">{_esc(room.name)} 墙砖四面展开（蓝=整砖　橙=收头　红=门窗套割　褐=阳角条）</text>',
    ]
    for i, w in enumerate(walls):
        col, row = i % 2, i // 2
        ox = pad + col * (cell_w + gap)
        oy = title_h + pad + row * (cell_h + label_h + gap)
        wl, wh = max(0.4, float(w.get("wall_len") or 1)), max(0.4, float(w.get("wall_h") or 1))
        s = min((cell_w - 16) / wl, (cell_h - 16) / wh)
        x0 = ox + (cell_w - wl * s) / 2
        y_floor = oy + label_h + 8 + wh * s  # screen y of floor line

        def sx(x: float) -> float:
            return x0 + x * s

        def sy(y: float) -> float:
            return y_floor - y * s

        parts.append(
            f'<text x="{ox + 8:.1f}" y="{oy + 16:.1f}" font-size="13" fill="#1b4f8a" '
            f'font-family="Microsoft YaHei, sans-serif">{_esc(w.get("name") or f"墙{i+1}")}　{wl:.2f}×{wh:.2f}m</text>'
        )
        parts.append(
            f'<rect x="{sx(0):.1f}" y="{sy(wh):.1f}" width="{wl*s:.1f}" height="{wh*s:.1f}" '
            f'fill="#f3f4f6" stroke="#111" stroke-width="1.5"/>'
        )
        for t in w.get("tiles") or []:
            fill = "#fca5a5" if t.get("sleeve") else ("#dbeafe" if t.get("full") else "#fed7aa")
            parts.append(
                f'<rect x="{sx(t["x"]):.1f}" y="{sy(t["y"]+t["h"]):.1f}" width="{t["w"]*s:.1f}" height="{t["h"]*s:.1f}" '
                f'fill="{fill}" stroke="#1e3a5f" stroke-width="0.6"/>'
            )
        parts.append(f'<line x1="{sx(0.02):.1f}" y1="{sy(0):.1f}" x2="{sx(0.02):.1f}" y2="{sy(wh):.1f}" stroke="#a16207" stroke-width="4"/>')
        parts.append(f'<line x1="{sx(wl-0.02):.1f}" y1="{sy(0):.1f}" x2="{sx(wl-0.02):.1f}" y2="{sy(wh):.1f}" stroke="#a16207" stroke-width="4"/>')
        parts.append(
            f'<text x="{sx(0.08):.1f}" y="{sy(0.16):.1f}" font-size="11" fill="#854d0e" '
            f'font-family="Microsoft YaHei, sans-serif">阳角条</text>'
        )
        for h in w.get("holes") or []:
            parts.append(
                f'<rect x="{sx(h["x"]):.1f}" y="{sy(h["y"]+h["h"]):.1f}" width="{h["w"]*s:.1f}" height="{h["h"]*s:.1f}" '
                f'fill="#f7f4ea" stroke="#b91c1c" stroke-width="1.6" stroke-dasharray="5 3"/>'
            )
            parts.append(
                f'<text x="{sx(h["x"]+h["w"]/2):.1f}" y="{sy(h["h"]/2):.1f}" font-size="11" fill="#b91c1c" '
                f'text-anchor="middle" font-family="Microsoft YaHei, sans-serif">门窗套割</text>'
            )
        for band in w.get("waterproof") or []:
            hy = float(band.get("h") or 0)
            parts.append(
                f'<line x1="{sx(0):.1f}" y1="{sy(hy):.1f}" x2="{sx(wl):.1f}" y2="{sy(hy):.1f}" '
                f'stroke="#0369a1" stroke-width="1" stroke-dasharray="5 3"/>'
            )
            parts.append(
                f'<text x="{sx(0.08):.1f}" y="{sy(hy)+12:.1f}" font-size="10" fill="#0c4a6e" '
                f'font-family="Microsoft YaHei, sans-serif">{_esc(band.get("label") or "")}</text>'
            )
    parts.append(
        f'<text x="{bw/2:.0f}" y="{bh-10:.0f}" text-anchor="middle" font-size="11" fill="#57534e" '
        f'font-family="Microsoft YaHei, sans-serif">GB 50327-2001 12.3.1：非整砖放阴角、每面不宜两列、边砖≥1/3、突出物整砖套割</text>'
    )
    body = "".join(parts)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw:.0f}" height="{bh:.0f}" viewBox="0 0 {bw:.0f} {bh:.0f}">'
        f"{body}</svg>"
    )


def svg_ceiling(room, ceil: dict[str, Any]) -> str:
    mode = "局部吊顶" if ceil.get("mode") == "local" else "满吊"
    p = PlanSvg(room.width, room.depth, f"{room.name} 吊顶排版  {ceil['kind']}  {mode}  主龙骨@{ceil['main_spacing']}m")
    p.rect(0, 0, room.width, room.depth, fill="#f8fafc", stroke="#111", sw=2)
    if ceil.get("mode") == "local":
        for r in ceil.get("drop_rects") or []:
            p.rect(r["x"], r["y"], r["w"], r["h"], fill="#e0f2fe", stroke="#0369a1", sw=1.5, opacity=0.55)
            p.text(r["x"] + r["w"] / 2, r["y"] + r["h"] / 2, "局部吊顶区", 12, fill="#0c4a6e")
    for pan in ceil["panels"]:
        fill = "#e2e8f0" if pan["cut"] else "#fff"
        p.rect(pan["x"], pan["y"], pan["w"], pan["h"], fill=fill, stroke="#64748b", sw=0.7)
    for e in ceil.get("edges") or []:
        p.line(e["x1"], e["y1"], e["x2"], e["y2"], stroke="#111", sw=2.5)
    for m in ceil["mains"]:
        p.line(m["x1"], m["y1"], m["x2"], m["y2"], stroke="#b45309", sw=2)
    for s in ceil["seconds"]:
        p.line(s["x1"], s["y1"], s["x2"], s["y2"], stroke="#0369a1", sw=1, dash="6 4")
    for e in ceil.get("extras") or []:
        p.line(e["x1"], e["y1"], e["x2"], e["y2"], stroke="#15803d", sw=1.5)
    for b in ceil.get("braces") or []:
        p.line(b["x1"], b["y1"], b["x2"], b["y2"], stroke="#dc2626", sw=1.4)
    if ceil.get("hanger_need_brace"):
        p.text(room.width / 2, 0.18, f"反支撑 GB 50210 7.1.11  吊杆{ceil.get('hanger_len_m', 0):.2f}m", 11, fill="#b91c1c")
    for h in ceil["hangers"]:
        p.circle(h["x"], h["y"], 0.06, fill="#111")
    for L in ceil["lights"]:
        p.circle(L["x"], L["y"], 0.12, fill="#fde68a")
    ht = ceil["hatch"]
    p.rect(ht["x"], ht["y"], ht["w"], ht["h"], fill="none", stroke="#dc2626", sw=1.5, dash="5 3")
    p.text(ht["x"] + ht["w"] / 2, ht["y"] + ht["h"] / 2, "检修口", 10, fill="#dc2626")
    p.text(0.12, 0.12, "图例：棕实线=主龙骨　蓝虚线=次龙骨　黑点=吊杆　黄圈=灯　绿线=附加龙骨　红虚框=检修口", 10, fill="#334155", anchor="start")
    return p.finish()


def svg_furniture(room, furn: dict[str, Any]) -> str:
    p = PlanSvg(room.width, room.depth, f"{room.name} 家具布置  {furn['kind']}")
    p.rect(0, 0, room.width, room.depth, fill="#f5f0e6", stroke="#111", sw=2)
    colors = ["#93c5fd", "#f9a8d4", "#fcd34d", "#86efac", "#c4b5fd", "#fda4af"]
    for i, it in enumerate(furn["items"]):
        p.rect(it["x"], it["y"], it["w"], it["d"], fill=colors[i % len(colors)], stroke="#1e3a5f", sw=1, opacity=0.9)
        p.text(it["x"] + it["w"] / 2, it["y"] + it["d"] / 2, it["name"], 11)
    for o in room.openings:
        if getattr(o, "kind", "door") != "door":
            continue
        label = f"门 {o.width*1000:.0f}"
        if o.wall == "S":
            p.rect(o.offset, 0, o.width, 0.08, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(o.offset + o.width / 2, 0.25, label, 10, fill="#b91c1c")
        elif o.wall == "N":
            p.rect(o.offset, room.depth - 0.08, o.width, 0.08, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(o.offset + o.width / 2, room.depth - 0.25, label, 10, fill="#b91c1c")
        elif o.wall == "W":
            p.rect(0, o.offset, 0.08, o.width, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(0.25, o.offset + o.width / 2, label, 10, fill="#b91c1c", anchor="start")
        elif o.wall == "E":
            p.rect(room.width - 0.08, o.offset, 0.08, o.width, fill="#f7f4ea", stroke="#b91c1c", sw=2)
            p.text(room.width - 0.25, o.offset + o.width / 2, label, 10, fill="#b91c1c")
    p.text(room.width / 2, -0.15, f"{room.width:.2f}m", 11)
    p.text(0.12, room.depth / 2, f"{room.depth:.2f}m", 11, anchor="start")
    return p.finish()
