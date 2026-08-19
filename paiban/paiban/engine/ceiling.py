from __future__ import annotations

import math
from typing import Any


def _axis_positions(length: float, max_spacing: float) -> list[float]:
    """Evenly space including both ends, each gap <= max_spacing."""
    n_gap = max(1, math.ceil(length / max_spacing - 1e-12))
    step = length / n_gap
    return [round(i * step, 5) for i in range(n_gap + 1)]


def _hangers_along(x1: float, y1: float, x2: float, y2: float, hanger_max: float, end: float) -> list[dict[str, float]]:
    """GB 50327 8.3.1 / GB 50210：吊杆距主龙骨端部不得超过 300mm；吊点间距应小于 1.2m."""
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length < 1e-6:
        return [{"x": x1, "y": y1}]
    ux, uy = dx / length, dy / length
    if length <= 2 * end + 0.05:
        dists = [0.0, length / 2, length]
    else:
        inner = max(length - 2 * end, 1e-6)
        gaps = max(1, math.ceil(inner / hanger_max - 1e-12))
        step = inner / gaps
        dists = [end + i * step for i in range(gaps + 1)]
        if abs(dists[-1] - (length - end)) > 1e-4:
            dists.append(length - end)
        if dists[0] > end + 1e-6:
            dists.insert(0, end)
    pts = []
    seen: set[tuple[float, float]] = set()
    for s in dists:
        px, py = round(x1 + ux * s, 4), round(y1 + uy * s, 4)
        key = (px, py)
        if key in seen:
            continue
        seen.add(key)
        pts.append({"x": px, "y": py})
    return pts


def _frame_rect(
    x0: float,
    y0: float,
    x1: float,
    y1: float,
    main_sp: float,
    sec_sp: float,
    hanger_max: float,
    end: float,
) -> dict[str, Any]:
    """Main keels span the short direction of this rectangle (短跨承力)."""
    rw, rd = x1 - x0, y1 - y0
    if rw < 0.05 or rd < 0.05:
        return {"mains": [], "seconds": [], "hangers": [], "span": min(rw, rd), "main_sp": main_sp, "sec_sp": sec_sp, "end_ok": True, "span_ok": True, "hanger_gaps": []}
    short_is_w = rw <= rd
    span = rw if short_is_w else rd
    long = rd if short_is_w else rw
    # 主龙骨沿短跨：龙骨长度 = 短向，间距沿长向
    main_pos = _axis_positions(long, main_sp)
    actual_main = main_pos[1] - main_pos[0] if len(main_pos) > 1 else long
    mains = []
    for pos in main_pos:
        if short_is_w:
            mains.append({"x1": x0, "y1": y0 + pos, "x2": x1, "y2": y0 + pos})
        else:
            mains.append({"x1": x0 + pos, "y1": y0, "x2": x0 + pos, "y2": y1})
    sec_pos = _axis_positions(span, sec_sp)
    actual_sec = sec_pos[1] - sec_pos[0] if len(sec_pos) > 1 else span
    seconds = []
    for pos in sec_pos:
        if short_is_w:
            seconds.append({"x1": x0 + pos, "y1": y0, "x2": x0 + pos, "y2": y1})
        else:
            seconds.append({"x1": x0, "y1": y0 + pos, "x2": x1, "y2": y0 + pos})
    hangers: list[dict[str, float]] = []
    hanger_gaps: list[float] = []
    end_ok = True
    span_ok = True
    for m in mains:
        pts = _hangers_along(m["x1"], m["y1"], m["x2"], m["y2"], hanger_max, end)
        hangers.extend(pts)
        if pts:
            d0 = math.hypot(pts[0]["x"] - m["x1"], pts[0]["y"] - m["y1"])
            d1 = math.hypot(pts[-1]["x"] - m["x2"], pts[-1]["y"] - m["y2"])
            if d0 > end + 0.005 or d1 > end + 0.005:
                end_ok = False
            for a, b in zip(pts, pts[1:]):
                g = math.hypot(b["x"] - a["x"], b["y"] - a["y"])
                hanger_gaps.append(g)
                if g >= 1.2 - 1e-6:
                    span_ok = False
    return {
        "mains": mains,
        "seconds": seconds,
        "hangers": hangers,
        "span": span,
        "main_sp": actual_main,
        "sec_sp": actual_sec,
        "end_ok": end_ok,
        "span_ok": span_ok,
        "hanger_gaps": hanger_gaps,
    }


def _gypsum_panels(room_w: float, room_d: float, pw: float, ph: float, clip: dict | None = None) -> list[dict[str, Any]]:
    panels: list[dict[str, Any]] = []
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
    if clip:
        cx, cy, cw, ch = clip["x"], clip["y"], clip["w"], clip["h"]
        kept = []
        for p in panels:
            x0 = max(p["x"], cx)
            y0 = max(p["y"], cy)
            x1 = min(p["x"] + p["w"], cx + cw)
            y1 = min(p["y"] + p["h"], cy + ch)
            if x1 - x0 > 0.02 and y1 - y0 > 0.02:
                q = dict(p)
                q.update({"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "cut": True})
                kept.append(q)
        return kept
    return panels


def _tile_panels(room_w: float, room_d: float, pw: float, ph: float, clip: dict | None = None) -> list[dict[str, Any]]:
    panels: list[dict[str, Any]] = []
    x = 0.0
    while x < room_w - 1e-9:
        w = min(pw, room_w - x)
        y = 0.0
        while y < room_d - 1e-9:
            h = min(ph, room_d - y)
            panels.append({"x": x, "y": y, "w": w, "h": h, "cut": abs(w - pw) > 0.01 or abs(h - ph) > 0.01})
            y += ph
        x += pw
    if clip:
        cx, cy, cw, ch = clip["x"], clip["y"], clip["w"], clip["h"]
        kept = []
        for p in panels:
            x0 = max(p["x"], cx)
            y0 = max(p["y"], cy)
            x1 = min(p["x"] + p["w"], cx + cw)
            y1 = min(p["y"] + p["h"], cy + ch)
            if x1 - x0 > 0.02 and y1 - y0 > 0.02:
                q = dict(p)
                q.update({"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0, "cut": True})
                kept.append(q)
        return kept
    return panels


def _local_drop_rect(room_w: float, room_d: float) -> dict[str, float]:
    """局部吊顶面积不应大于使用面积 1/3（GB 55038-2025 4.1.2-2）。沿长边做灯槽带。"""
    area = room_w * room_d
    max_local = area / 3
    long_is_d = room_d >= room_w
    long = room_d if long_is_d else room_w
    short = room_w if long_is_d else room_d
    band = min(0.80, max_local / short)
    band = max(0.45, band)
    if short * band > max_local + 1e-6:
        band = max_local / short
    if long_is_d:
        return {"x": 0.0, "y": room_d - band, "w": room_w, "h": band}
    return {"x": room_w - band, "y": 0.0, "w": band, "h": room_d}


def layout_ceiling(
    room_w: float,
    room_d: float,
    spec: dict[str, Any],
    lights: int | None = None,
    wet: bool = False,
    room_height: float = 2.8,
    room_kind: str = "客厅",
) -> dict[str, Any]:
    kind = spec["kind"]
    pw, ph = spec["panel_w"], spec["panel_h"]
    # GB 50327-2001：次龙骨不得大于 600mm；潮湿场所宜 300～400mm
    sec_limit = 0.40 if wet else 0.60
    sec_sp = min(float(spec.get("secondary") or 0.4), sec_limit)
    if wet:
        sec_sp = min(max(sec_sp, 0.30), 0.40)
    main_sp = min(float(spec.get("main") or 1.0), 1.0 if kind == "石膏板" else float(spec.get("panel_w") or 0.6))
    hanger_max = 1.19  # 应小于 1.2m
    end = 0.30
    drop = 0.20 if kind == "石膏板" else 0.12
    living = room_kind in ("客厅", "卧室", "餐厅", "书房")
    hmin = 2.60 if living else 2.20
    net_full = round(room_height - drop, 3)
    mode = "full"
    drop_rects: list[dict[str, float]] = [{"x": 0.0, "y": 0.0, "w": room_w, "h": room_d}]
    net_main = net_full
    net_local = net_full
    reason = ""
    if net_full + 1e-6 < hmin and living and (room_height - drop) + 1e-6 >= 2.20:
        # 满吊后低于 2.60m：改为局部吊顶，局部净高 ≥2.20 且面积 ≤1/3
        mode = "local"
        drop_rects = [_local_drop_rect(room_w, room_d)]
        net_main = round(room_height, 3)
        net_local = net_full
        reason = f"层高 {room_height}m 满吊后净高 {net_full}m < 2.60m，按 GB 55038-2025 4.1.2 改为局部吊顶"
    elif net_full + 1e-6 < hmin:
        reason = f"吊顶后净高 {net_full}m 低于 {hmin:.2f}m 下限"

    clip = drop_rects[0] if mode == "local" else None
    if kind == "石膏板":
        panels = _gypsum_panels(room_w, room_d, pw, ph, clip)
    else:
        panels = _tile_panels(room_w, room_d, pw, ph, clip)

    mains: list[dict[str, float]] = []
    seconds: list[dict[str, float]] = []
    hangers: list[dict[str, float]] = []
    hanger_gaps: list[float] = []
    end_ok = True
    span_ok = True
    actual_main = main_sp
    actual_sec = sec_sp
    span = min(room_w, room_d)
    for r in drop_rects:
        fr = _frame_rect(r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"], main_sp, sec_sp, hanger_max, end)
        mains.extend(fr["mains"])
        seconds.extend(fr["seconds"])
        hangers.extend(fr["hangers"])
        hanger_gaps.extend(fr["hanger_gaps"])
        end_ok = end_ok and fr["end_ok"]
        span_ok = span_ok and fr["span_ok"]
        actual_main = fr["main_sp"]
        actual_sec = fr["sec_sp"]
        span = fr["span"]

    n_light = lights if lights is not None else max(1, round(room_w * room_d / 8))
    if mode == "local":
        n_light = max(2, min(n_light, 6))
    light_pts = []
    extras = []
    if mode == "full":
        cols = max(1, round(room_w / 2.4))
        rows = max(1, math.ceil(n_light / cols))
        for i in range(cols):
            for j in range(rows):
                if len(light_pts) >= n_light:
                    break
                lx = (i + 0.5) * room_w / cols
                ly = (j + 0.5) * room_d / rows
                light_pts.append({"x": lx, "y": ly, "kind": "灯"})
                extras.append({"x1": max(0, lx - 0.3), "y1": ly, "x2": min(room_w, lx + 0.3), "y2": ly})
    else:
        r = drop_rects[0]
        n = max(2, n_light)
        for i in range(n):
            lx = r["x"] + (i + 0.5) * r["w"] / n
            ly = r["y"] + r["h"] / 2
            light_pts.append({"x": lx, "y": ly, "kind": "灯"})
            extras.append({"x1": max(r["x"], lx - 0.25), "y1": ly, "x2": min(r["x"] + r["w"], lx + 0.25), "y2": ly})

    hatch_rect = drop_rects[0]
    hx = hatch_rect["x"] + 0.15
    hy = hatch_rect["y"] + 0.15
    hatch = {"x": hx, "y": hy, "w": 0.6, "h": 0.6}
    if hx + 0.6 > hatch_rect["x"] + hatch_rect["w"]:
        hatch["x"] = max(hatch_rect["x"], hatch_rect["x"] + hatch_rect["w"] - 0.65)
    if hy + 0.6 > hatch_rect["y"] + hatch_rect["h"]:
        hatch["y"] = max(hatch_rect["y"], hatch_rect["y"] + hatch_rect["h"] - 0.65)
        if hatch_rect["h"] < 0.62:
            hatch["h"] = max(0.4, hatch_rect["h"] - 0.1)
            hatch["w"] = max(0.4, min(0.6, hatch_rect["w"] - 0.1))
    camber = round(span * 0.002, 4)
    stagger = kind != "石膏板" or _has_stagger(panels)
    local_area = sum(r["w"] * r["h"] for r in drop_rects)
    room_area = room_w * room_d
    net_height = net_main if mode == "local" else net_full
    edges = []
    for r in drop_rects:
        x0, y0, x1, y1 = r["x"], r["y"], r["x"] + r["w"], r["y"] + r["h"]
        edges.extend([
            {"x1": x0, "y1": y0, "x2": x1, "y2": y0},
            {"x1": x0, "y1": y1, "x2": x1, "y2": y1},
            {"x1": x0, "y1": y0, "x2": x0, "y2": y1},
            {"x1": x1, "y1": y0, "x2": x1, "y2": y1},
        ])

    return {
        "kind": kind,
        "spec": spec,
        "mode": mode,
        "reason": reason,
        "panels": panels,
        "mains": mains,
        "seconds": seconds,
        "edges": edges,
        "extras": extras,
        "hangers": hangers,
        "lights": light_pts,
        "hatch": hatch,
        "drop_rects": drop_rects,
        "main_spacing": round(actual_main, 3),
        "secondary_spacing": round(actual_sec, 3),
        "hanger_max": round(max(hanger_gaps) if hanger_gaps else 0.0, 3),
        "hanger_end_ok": end_ok,
        "hanger_span_ok": span_ok,
        "camber_m": camber,
        "span_m": round(span, 3),
        "drop_m": drop,
        "net_height": net_height,
        "net_full": net_full,
        "net_local": net_local,
        "local_area": round(local_area, 3),
        "local_area_ratio": round(local_area / room_area, 3) if room_area else 1,
        "wet": wet,
        "stagger": stagger,
        "panel_count": len(panels),
        "hanger_count": len(hangers),
        "sec_limit": sec_limit,
        "hmin": hmin,
        "room_kind": room_kind,
        "hanger_need_brace": drop > 1.5,
    }


def _has_stagger(panels: list[dict[str, Any]]) -> bool:
    rows: dict[float, list[float]] = {}
    for p in panels:
        rows.setdefault(round(p["y"], 2), []).append(round(p["x"], 2))
    keys = sorted(rows)
    for a, b in zip(keys, keys[1:]):
        if rows[a] and rows[b] and set(rows[a]) == set(rows[b]) and len(rows[a]) > 1:
            return False
    return True
