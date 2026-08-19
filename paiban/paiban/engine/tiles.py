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
    max_cut_cols: int = 2,
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
    if max_cut_cols <= 1:
        two = None
    if prefer_symmetric and two and min(two[0], two[-1]) + 1e-6 >= tile / 3 and max_cut_cols >= 2:
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
        "offset": 0.0, "widths": widths, "ok": mine + 1e-6 >= tile / 3 and n_cut <= max_cut_cols,
        "min": mine, "n": len(widths), "n_cut": n_cut, "mode": mode,
        "at_corner": mode in ("whole", "one_cut", "two_ends", "single"),
    }


def _tile(x, y, w, h, tw, th, rotate=0, sleeve=False):
    full = abs(w - tw) < 0.004 and abs(h - th) < 0.004
    return {
        "x": round(x, 5), "y": round(y, 5), "w": round(w, 5), "h": round(h, 5),
        "full": full and not sleeve, "cut": not full or sleeve, "rotate": rotate, "sleeve": sleeve, "tw": tw, "th": th,
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
    gx_w = gx.get("widths") or [tw]
    gy_w = gy.get("widths") or [th]
    min_edge = min(min(gx_w), min(gy_w)) if gx_w and gy_w else 0.0
    if gx.get("min") is not None:
        min_edge = min(min_edge, float(gx["min"]))
    if gy.get("min") is not None:
        min_edge = min(min_edge, float(gy["min"]))
    first = gy_w[0] if gy_w else th
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


def _main_door(openings, room_w: float, room_d: float):
    doors = [o for o in (openings or []) if getattr(o, "kind", "door") == "door"]
    if not doors:
        class _D:
            wall, offset, width, height, kind = "S", max(0.1, room_w / 2 - 0.4), 0.8, 2.1, "door"
        return _D()
    return max(doors, key=lambda o: float(getattr(o, "width", 0.8)))


def _map_from_door_frame(x: float, y: float, w: float, h: float, wall: str, room_w: float, room_d: float):
    """Local frame: door on y=0, +y into the room, +x along the door wall."""
    if wall == "S":
        return x, y, w, h
    if wall == "N":
        return x, room_d - y - h, w, h
    if wall == "W":
        return y, x, h, w
    return room_w - y - h, x, h, w


def _brick_rows(length: float, tile: float, grout: float, n_rows: int, row_heights: list[float]) -> list[list[float]]:
    """工字/1/3 错缝，边条仍 ≥ 整砖 1/3。"""
    base = cover_gb50327(length, tile, grout, cut_at="end", prefer_symmetric=True)
    even = base["widths"]
    min_cut = tile / 3
    best_odd = None
    for frac in (1 / 3, 1 / 2, 2 / 3):
        shift = (tile + grout) * frac
        widths: list[float] = []
        x = -shift
        step = max(0.05, tile + grout)
        while x < length - 1e-9:
            x0, x1 = max(0.0, x), min(length, x + tile)
            if x1 - x0 > 1e-6:
                widths.append(round(x1 - x0, 5))
            x += step
        if not widths:
            continue
        if min(widths) + 1e-6 >= min_cut:
            best_odd = widths
            break
    if best_odd is None:
        best_odd = even
    return [best_odd if i % 2 else even for i, _h in enumerate(row_heights)]


def layout_floor(room_w, room_d, tw, th, grout, pattern="straight", openings=None, kind: str = "客厅"):
    room_w, room_d = float(room_w), float(room_d)
    if max(room_w, room_d) >= 80:
        room_w, room_d = room_w / 1000.0, room_d / 1000.0
    tw, th = max(0.05, float(tw)), max(0.05, float(th))
    door = _main_door(openings, room_w, room_d)
    wall = getattr(door, "wall", "S") or "S"
    along, into = (room_w, room_d) if wall in ("S", "N") else (room_d, room_w)
    along_tile, into_tile = (tw, th) if wall in ("S", "N") else (th, tw)

    herringbone_note = ""
    if pattern == "herringbone":
        pattern = "diagonal"
        herringbone_note = "人字/鱼骨铺本软件按 45° 斜铺近似（现场须按人字放样，不假装已排出人字缝）；"

    if "地板" in kind or pattern == "laminate":
        return _layout_laminate(room_w, room_d, tw, th, grout, wall)

    gx = cover_gb50327(along, along_tile, grout, cut_at="end", prefer_symmetric=True)
    gy = cover_gb50327(into, into_tile, grout, cut_at="end", prefer_symmetric=False)

    local_tiles: list[dict[str, Any]] = []
    extra = ""
    if pattern == "diagonal":
        diag = math.hypot(tw, th) / math.sqrt(2)
        gx = cover_gb50327(along, diag, grout, prefer_symmetric=True)
        gy = cover_gb50327(into, diag, grout, cut_at="end")
        local_tiles = _grid_tiles(gx, gy, diag, diag, grout, rotate=45)
        extra = herringbone_note + "斜铺 45°；非整砖仍按阴角收头（GB 50327 12.3.1 精神 / 14.3.1 十字线）"
        tw, th = diag, diag
        along_tile, into_tile = diag, diag
    elif pattern == "brick":
        rows = _brick_rows(along, along_tile, grout, len(gy["widths"]), gy["widths"])
        y = 0.0
        for h, widths in zip(gy["widths"], rows):
            x = 0.0
            for w in widths:
                local_tiles.append(_tile(x, y, w, h, along_tile, into_tile))
                x += w + grout
            y += h + grout
        all_w = [w for row in rows for w in row]
        gx = {
            "widths": rows[0],
            "n_cut": max(sum(1 for w in row if abs(w - along_tile) > 0.004) for row in rows),
            "mode": "brick",
            "at_corner": True,
            "min": min(all_w) if all_w else along_tile,
        }
        extra = "工字/1/3 错缝；进深从门口整砖、远端阴角收头；错缝边条仍 ≥1/3"
    else:
        local_tiles = _grid_tiles(gx, gy, along_tile, into_tile, grout)
        extra = "正铺；沿门口拉十字线；进口第一皮整砖，非整砖放对墙阴角（GB 50327 14.3.1 / 12.3.1）"

    tiles = []
    for t in local_tiles:
        wx, wy, ww, wh = _map_from_door_frame(t["x"], t["y"], t["w"], t["h"], wall, room_w, room_d)
        nt = dict(t)
        nt.update({"x": round(wx, 5), "y": round(wy, 5), "w": round(ww, 5), "h": round(wh, 5)})
        tiles.append(nt)
    pack = _pack(pattern, along_tile, into_tile, grout, gx, gy, tiles, extra=extra)
    pack["door_wall"] = wall
    pack["tile_w"] = tw if pattern != "diagonal" else pack["tile_w"]
    pack["tile_h"] = th if pattern != "diagonal" else pack["tile_h"]
    return pack


def _layout_laminate(room_w, room_d, tw, th, grout, wall: str):
    """GB 50327-2001 14.3.3：相邻条板端头错缝距离应大于 300mm。"""
    along, into = (room_w, room_d) if wall in ("S", "N") else (room_d, room_w)
    board_w, board_l = (min(tw, th), max(tw, th))
    stagger = max(0.301, board_l / 3)
    gy = cover_gb50327(into, board_w, grout, cut_at="end", prefer_symmetric=False)
    tiles = []
    y = 0.0
    for i, h in enumerate(gy["widths"]):
        shift = stagger if i % 2 else 0.0
        x = -shift
        step = max(0.05, board_l + grout)
        while x < along - 1e-9:
            x0, x1 = max(0.0, x), min(along, x + board_l)
            if x1 > x0 + 0.02:
                wx, wy, ww, wh = _map_from_door_frame(x0, y, x1 - x0, h, wall, room_w, room_d)
                tiles.append(_tile(wx, wy, ww, wh, board_l, board_w))
            x += step
        y += h + grout
    ends = [min(t["w"], t["h"]) for t in tiles] or [board_w]
    gx = {"widths": [board_l], "n_cut": 1, "mode": "laminate", "at_corner": True, "min": min(ends)}
    pack = _pack("laminate", board_l, board_w, grout, gx, gy, tiles, extra="强化地板：相邻条板端头错缝距离应大于 300mm（GB 50327 14.3.3）")
    pack["stagger_m"] = stagger
    pack["door_wall"] = wall
    pack["min_end_joint_stagger_m"] = stagger
    return pack


def wet_floor_features(room_w, room_d, openings=None, kind="卫生间", tiles=None):
    doors = [o for o in (openings or []) if getattr(o, "kind", "door") == "door"]
    door = max(doors, key=lambda o: float(getattr(o, "width", 0))) if doors else None
    door_x = room_w / 2
    ramp = {"x": (room_w - 0.70) / 2, "y": 0.0, "w": 0.70, "d": 0.30, "drop_mm": 15}
    if door:
        wall, off, dw = getattr(door, "wall", "S"), float(getattr(door, "offset", 0)), float(getattr(door, "width", 0.7))
        if wall == "S":
            door_x = off + dw / 2
            ramp = {"x": off, "y": 0.0, "w": dw, "d": 0.30, "drop_mm": 15}
        elif wall == "N":
            door_x = off + dw / 2
            ramp = {"x": off, "y": room_d - 0.30, "w": dw, "d": 0.30, "drop_mm": 15}
        elif wall == "W":
            door_x = 0.15
            ramp = {"x": 0.0, "y": off, "w": 0.30, "d": dw, "drop_mm": 15}
        else:
            door_x = room_w - 0.15
            ramp = {"x": room_w - 0.30, "y": off, "w": 0.30, "d": dw, "drop_mm": 15}
    drain = None
    if kind == "卫生间":
        full = [t for t in (tiles or []) if t.get("full") and t["y"] + t["h"] / 2 > room_d * 0.40]
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
        "waterproof_floor": kind in ("卫生间", "厨房", "阳台"),
    }


def layout_wall(wall_len, wall_h, tw, th, grout, holes=None):
    gx = cover_gb50327(wall_len, tw, grout, cut_at="end", prefer_symmetric=False, max_cut_cols=1)
    gy = cover_gb50327(wall_h, th, grout, cut_at="end", prefer_symmetric=False)
    holes = holes or []
    if holes and gx.get("mode") == "one_cut" and gx["widths"]:
        cut_at_start = abs(gx["widths"][0] - tw) > 0.004
        for hole in holes:
            hx0, hx1 = hole["x"], hole["x"] + hole["w"]
            col0, col1 = (0.0, gx["widths"][0]) if cut_at_start else (wall_len - gx["widths"][-1], wall_len)
            if not (col1 < hx0 - 0.02 or col0 > hx1 + 0.02):
                gx = cover_gb50327(wall_len, tw, grout, cut_at="start" if not cut_at_start else "end", prefer_symmetric=False, max_cut_cols=1)
                break
    tiles = _sleeve_holes(_grid_tiles(gx, gy, tw, th, grout), holes, tw, th)
    pack = _pack("wall", tw, th, grout, gx, gy, tiles, extra="非整砖放阴角且每面只一列；门窗洞口整砖套割（GB 50327 12.3.1 / GB 50210-2018 10.2.6）")
    pack.update({"holes": holes, "wall_len": wall_len, "wall_h": wall_h, "corner_trim": True, "sleeved": sum(1 for t in tiles if t.get("sleeve"))})
    return pack
