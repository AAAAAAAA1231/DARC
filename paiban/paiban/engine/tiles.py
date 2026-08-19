from __future__ import annotations

import math
from typing import Any


def _all_whole(length: float, tile: float, grout: float) -> list[float] | None:
    if tile <= 0:
        return None
    k = max(1, int(round((length + grout) / (tile + grout))))
    total = k * tile + (k - 1) * grout
    if abs(total - length) < 0.004:
        return [tile] * k
    return None


def _one_cut(length: float, tile: float, grout: float, cut_at: str) -> list[float] | None:
    """n whole tiles + one cut in [tile/3, tile]. GB 50327-2001 12.3.1."""
    min_cut = tile / 3
    nmax = max(0, int((length + 1e-9) / (tile + grout)))
    for n in range(nmax, -1, -1):
        cut = length - n * tile - n * grout
        if cut < min_cut - 1e-6 or cut > tile + 0.004:
            continue
        if abs(cut - tile) < 0.004:
            widths = [tile] * (n + 1)
        elif cut_at == "start":
            widths = [round(cut, 5)] + [tile] * n
        else:
            widths = [tile] * n + [round(cut, 5)]
        if widths and abs(sum(widths) + grout * (len(widths) - 1) - length) < 0.008:
            return widths
    return None


def _two_end_cuts(length: float, tile: float, grout: float) -> list[float] | None:
    min_cut = tile / 3
    kmax = max(2, int((length + 1e-9) / (tile + grout)) + 3)
    best = None
    for k in range(2, kmax + 1):
        rem = length - (k - 2) * tile - (k - 1) * grout
        if rem < 2 * min_cut - 1e-6 or rem > 2 * tile + 0.008:
            continue
        c = rem / 2
        if min_cut - 1e-6 <= c <= tile + 0.004:
            widths = [round(c, 5)] + [tile] * (k - 2) + [round(c, 5)]
            err = abs(sum(widths) + grout * (len(widths) - 1) - length)
            if best is None or err < best[0]:
                best = (err, widths)
    return None if best is None else best[1]


def cover_gb50327(
    length: float,
    tile: float,
    grout: float,
    *,
    cut_at: str = "end",
    prefer_symmetric: bool = False,
) -> dict[str, Any]:
    """GB 50327-2001 12.3.1: 阴角收头、不宜两列非整砖、边砖≥1/3。"""
    if length <= tile + 1e-9:
        cut = abs(length - tile) > 0.004
        return {
            "offset": 0.0, "widths": [length], "ok": length + 1e-6 >= tile / 3,
            "min": length, "n": 1, "n_cut": 1 if cut else 0, "mode": "single", "at_corner": True,
        }
    whole = _all_whole(length, tile, grout)
    if whole:
        return {"offset": 0.0, "widths": whole, "ok": True, "min": min(whole), "n": len(whole), "n_cut": 0, "mode": "whole", "at_corner": True}
    one = _one_cut(length, tile, grout, cut_at)
    two = _two_end_cuts(length, tile, grout)
    if prefer_symmetric and two and min(two[0], two[-1]) + 1e-6 >= tile / 3:
        widths, mode = two, "two_ends"
    elif one:
        widths, mode = one, "one_cut"
    elif two:
        widths, mode = two, "two_ends"
    else:
        widths, mode = [length], "fail"
    n_cut = sum(1 for w in widths if abs(w - tile) > 0.004)
    mine = min(widths)
    return {
        "offset": 0.0, "widths": widths, "ok": mine + 1e-6 >= tile / 3 and n_cut <= 2,
        "min": mine, "n": len(widths), "n_cut": n_cut, "mode": mode,
        "at_corner": mode in ("whole", "one_cut", "two_ends", "single"),
    }


def _grid_tiles(gx, gy, tw, th, grout, rotate=0):
    tiles = []
    y = 0.0
    for h in gy["widths"]:
        x = 0.0
        for w in gx["widths"]:
            tiles.append(_tile(x, y, w, h, tw, th, rotate))
            x += w + grout
        y += h + grout
    return tiles


def _tile(x, y, w, h, tw, th, rotate=0, sleeve=False):
    full = abs(w - tw) < 0.004 and abs(h - th) < 0.004
    return {
        "x": round(x, 5), "y": round(y, 5), "w": round(w, 5), "h": round(h, 5),
        "full": full and not sleeve, "cut": not full or sleeve, "rotate": rotate, "sleeve": sleeve, "tw": tw, "th": th,
    }


def _subtract_rect(x, y, w, h, hx, hy, hw, hh):
    x1, y1, hx1, hy1 = x + w, y + h, hx + hw, hy + hh
    ix0, iy0, ix1, iy1 = max(x, hx), max(y, hy), min(x1, hx1), min(y1, hy1)
    if ix0 >= ix1 - 1e-9 or iy0 >= iy1 - 1e-9:
        return [(x, y, w, h)]
    out = []
    if iy0 > y + 1e-6:
        out.append((x, y, w, iy0 - y))
    if y1 > iy1 + 1e-6:
        out.append((x, iy1, w, y1 - iy1))
    if ix0 > x + 1e-6:
        out.append((x, iy0, ix0 - x, iy1 - iy0))
    if x1 > ix1 + 1e-6:
        out.append((ix1, iy0, x1 - ix1, iy1 - iy0))
    return out


def _sleeve_holes(tiles, holes, tw, th):
    if not holes:
        return tiles
    kept = []
    for t in tiles:
        rects = [(t["x"], t["y"], t["w"], t["h"])]
        hit = False
        for hole in holes:
            nxt = []
            for r in rects:
                parts = _subtract_rect(r[0], r[1], r[2], r[3], hole["x"], hole["y"], hole["w"], hole["h"])
                if len(parts) != 1 or abs(parts[0][0] - r[0]) > 1e-9 or abs(parts[0][2] - r[2]) > 1e-9:
                    hit = True
                nxt.extend(parts)
            rects = nxt
        for x, y, w, h in rects:
            if w > 0.012 and h > 0.012:
                kept.append(_tile(x, y, w, h, tw, th, t.get("rotate", 0), sleeve=hit))
    return kept


def _pack(pattern, tw, th, grout, gx, gy, tiles, extra=""):
    n = len(tiles)
    cuts = sum(1 for t in tiles if t["cut"])
    area = sum(t["w"] * t["h"] for t in tiles)
    # 12.3.1 边列宽度看排砖网格，不含门窗套割碎砖
    gx_w = gx.get("widths") or [tw]
    gy_w = gy.get("widths") or [th]
    min_edge = min(min(gx_w), min(gy_w))
    first = gy_w[0]
    return {
        "pattern": pattern, "tiles": tiles, "count": n, "cuts": cuts, "full": n - cuts,
        "area": round(area, 3), "waste_m2": round(max(0.0, n * tw * th - area), 3),
        "grout": grout, "tile_w": tw, "tile_h": th, "gx": gx, "gy": gy,
        "min_edge": round(min_edge, 4), "n_cut_cols": gx.get("n_cut", 0), "n_cut_rows": gy.get("n_cut", 0),
        "cut_mode_x": gx.get("mode"), "cut_mode_y": gy.get("mode"),
        "cuts_at_corner": bool(gx.get("at_corner") and gy.get("at_corner")),
        "first_row_whole_from_door": abs(first - th) < 0.006,
        "note": extra,
    }


def layout_floor(room_w, room_d, tw, th, grout, pattern="straight", openings=None):
    gx = cover_gb50327(room_w, tw, grout, cut_at="end", prefer_symmetric=True)
    gy = cover_gb50327(room_d, th, grout, cut_at="end", prefer_symmetric=False)
    if pattern == "diagonal":
        diag = math.hypot(tw, th) / math.sqrt(2)
        gx = cover_gb50327(room_w, diag, grout, prefer_symmetric=True)
        gy = cover_gb50327(room_d, diag, grout, cut_at="end")
        tiles = [t for t in _grid_tiles(gx, gy, diag, diag, grout, rotate=45) if t["w"] > 0.02]
        return _pack("diagonal", tw, th, grout, gx, gy, tiles, extra="斜铺 45°；非整砖仍按阴角收头")
    if pattern == "brick":
        tiles = []
        y = 0.0
        row = 0
        for h in gy["widths"]:
            shift = (tw + grout) / 3 if row % 2 else 0.0
            x = -shift
            while x < room_w - 1e-9:
                x0, x1 = max(0.0, x), min(room_w, x + tw)
                if x1 > x0:
                    tiles.append(_tile(x0, y, x1 - x0, h, tw, th))
                x += tw + grout
            y += h + grout
            row += 1
        return _pack("brick", tw, th, grout, gx, gy, tiles, extra="工字错缝；进深仍按门口整砖、远端阴角收头")
    tiles = _grid_tiles(gx, gy, tw, th, grout)
    extra = "人字纹按阴角收头示意" if pattern == "herringbone" else "正铺；开间分中；门口向内整砖，非整砖放远端阴角（GB 50327 12.3.1）"
    return _pack(pattern if pattern != "herringbone" else "herringbone", tw, th, grout, gx, gy, tiles, extra=extra)


def wet_floor_features(room_w, room_d, openings=None, kind="卫生间", tiles=None):
    doors = [o for o in (openings or []) if getattr(o, "kind", "door") == "door"]
    door = doors[0] if doors else None
    door_x = room_w / 2
    ramp = {"x": (room_w - 0.70) / 2, "y": 0.0, "w": 0.70, "d": 0.30, "drop_mm": 15}
    if door:
        wall, off, dw = getattr(door, "wall", "S"), float(getattr(door, "offset", 0)), float(getattr(door, "width", 0.7))
        door_x = off + dw / 2
        if wall == "S":
            ramp = {"x": off, "y": 0.0, "w": dw, "d": 0.30, "drop_mm": 15}
        elif wall == "N":
            ramp = {"x": off, "y": room_d - 0.30, "w": dw, "d": 0.30, "drop_mm": 15}
        elif wall == "W":
            ramp = {"x": 0.0, "y": off, "w": 0.30, "d": dw, "drop_mm": 15}
        else:
            ramp = {"x": room_w - 0.30, "y": off, "w": 0.30, "d": dw, "drop_mm": 15}
    drain = None
    if kind == "卫生间":
        full = [t for t in (tiles or []) if t.get("full") and t["y"] + t["h"] / 2 > room_d * 0.45]
        if full:
            pick = max(full, key=lambda t: (t["y"] + t["h"] / 2, -abs(t["x"] + t["w"] / 2 - door_x)))
            drain = {"x": round(pick["x"] + pick["w"] / 2, 3), "y": round(pick["y"] + pick["h"] / 2, 3), "sleeved": True}
        else:
            drain = {"x": round(min(max(room_w * 0.72, 0.4), room_w - 0.35), 3), "y": round(min(room_d - 0.35, room_d * 0.75), 3), "sleeved": False}
    dx, dy = (drain or {}).get("x", room_w / 2), (drain or {}).get("y", room_d / 2)
    dmax = max(math.hypot(x - dx, y - dy) for x, y in ((0, 0), (room_w, 0), (0, room_d), (room_w, room_d)))
    return {
        "drain": drain, "slope_pct": 1.0 if kind == "卫生间" else 0.0,
        "full_room_fall_mm": round(dmax * 10, 1), "local_slope": bool(kind == "卫生间" and dmax * 0.01 > 0.015),
        "door_step_mm": 15, "ramp": ramp, "kind": kind, "cross_x": round(door_x, 3), "cross_y": round(room_d / 2, 3),
    }


def layout_wall(wall_len, wall_h, tw, th, grout, holes=None):
    gx = cover_gb50327(wall_len, tw, grout, cut_at="end", prefer_symmetric=False)
    gy = cover_gb50327(wall_h, th, grout, cut_at="end", prefer_symmetric=False)
    holes = holes or []
    tiles = _sleeve_holes(_grid_tiles(gx, gy, tw, th, grout), holes, tw, th)
    pack = _pack("wall", tw, th, grout, gx, gy, tiles, extra="非整砖放阴角；门窗洞口整砖套割（GB 50327 12.3.1）")
    pack.update({"holes": holes, "wall_len": wall_len, "wall_h": wall_h, "corner_trim": True, "sleeved": sum(1 for t in tiles if t.get("sleeve"))})
    return pack
