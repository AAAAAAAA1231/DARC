from __future__ import annotations

from typing import Any


def layout_ceiling(room_w: float, room_d: float, spec: dict[str, Any], lights: int | None = None) -> dict[str, Any]:
    pw, ph = spec["panel_w"], spec["panel_h"]
    kind = spec["kind"]
    panels = []
    if kind == "石膏板":
        # 长边沿房间长向，错缝 1.2m
        y = 0.0
        row = 0
        while y < room_d - 1e-9:
            h = min(ph, room_d - y)
            x = 0.6 if row % 2 else 0.0
            if x > 0:
                panels.append({"x": 0.0, "y": y, "w": min(x, room_w), "h": h, "cut": True})
            while x < room_w - 1e-9:
                w = min(pw, room_w - x)
                panels.append({"x": x, "y": y, "w": w, "h": h, "cut": w < pw - 0.01 or h < ph - 0.01})
                x += pw
            y += ph
            row += 1
    else:
        x = 0.0
        while x < room_w - 1e-9:
            w = min(pw, room_w - x)
            y = 0.0
            while y < room_d - 1e-9:
                h = min(ph, room_d - y)
                panels.append({"x": x, "y": y, "w": w, "h": h, "cut": abs(w - pw) > 0.01 or abs(h - ph) > 0.01})
                y += ph
            x += pw

    mains, seconds, hangers = [], [], []
    # 主龙骨沿短跨
    short_is_w = room_w <= room_d
    span = room_w if short_is_w else room_d
    long = room_d if short_is_w else room_w
    main_sp = spec["main"]
    n_main = max(1, round(span / main_sp))
    actual_main = span / n_main if n_main else span
    for i in range(n_main + 1):
        pos = min(span, i * actual_main)
        if short_is_w:
            mains.append({"x1": pos, "y1": 0, "x2": pos, "y2": room_d})
        else:
            mains.append({"x1": 0, "y1": pos, "x2": room_w, "y2": pos})
    sec_sp = spec["secondary"]
    n_sec = max(1, round(long / sec_sp))
    actual_sec = long / n_sec if n_sec else long
    for i in range(n_sec + 1):
        pos = min(long, i * actual_sec)
        if short_is_w:
            seconds.append({"x1": 0, "y1": pos, "x2": room_w, "y2": pos})
        else:
            seconds.append({"x1": pos, "y1": 0, "x2": pos, "y2": room_d})
    hang_sp = spec["hanger"]
    edge = spec["edge"]
    xs = _axis(room_w, hang_sp, edge)
    ys = _axis(room_d, hang_sp, edge)
    for x in xs:
        for y in ys:
            hangers.append({"x": x, "y": y})

    n_light = lights if lights is not None else max(1, round(room_w * room_d / 8))
    light_pts = []
    cols = max(1, round(room_w / 2.4))
    rows = max(1, n_light // cols or 1)
    for i in range(max(1, cols)):
        for j in range(max(1, rows)):
            light_pts.append({"x": (i + 0.5) * room_w / cols, "y": (j + 0.5) * room_d / rows, "kind": "灯"})
    # 检修口放角落避开主视面
    hatch = {"x": 0.3, "y": 0.3, "w": 0.6, "h": 0.6}

    return {
        "kind": kind,
        "spec": spec,
        "panels": panels,
        "mains": mains,
        "seconds": seconds,
        "hangers": hangers,
        "lights": light_pts[:n_light] if n_light else light_pts[:1],
        "hatch": hatch,
        "main_spacing": round(actual_main, 3),
        "secondary_spacing": round(actual_sec, 3),
        "panel_count": len(panels),
        "hanger_count": len(hangers),
    }


def _axis(length: float, spacing: float, edge: float) -> list[float]:
    pts = [min(edge, length / 2)]
    x = pts[0]
    while x + spacing < length - edge / 2:
        x += spacing
        pts.append(min(x, length - min(edge, length / 2)))
    end = length - min(edge, length / 2)
    if abs(pts[-1] - end) > 0.05:
        pts.append(end)
    return pts
