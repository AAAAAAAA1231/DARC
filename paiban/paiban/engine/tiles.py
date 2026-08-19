from __future__ import annotations

import math
from typing import Any


def _cover_1d(length: float, tile: float, grout: float, min_frac: float = 1 / 3) -> dict[str, Any]:
    """Search offset so both end pieces >= min_frac of tile when possible."""
    pitch = tile + grout
    if length <= tile:
        return {"offset": 0.0, "widths": [length], "ok": length >= tile * min_frac - 1e-6, "n": 1}

    best = None
    steps = 48
    for i in range(steps + 1):
        ox = -tile * i / steps
        widths = []
        x = ox
        guard = 0
        while x < length - 1e-9 and guard < 400:
            x0, x1 = max(0.0, x), min(length, x + tile)
            if x1 - x0 > 1e-6:
                widths.append(round(x1 - x0, 5))
            x += pitch
            guard += 1
        if not widths:
            continue
        mine = min(widths)
        waste = sum(max(0.0, tile - w) for w in widths)
        score = (mine, -len(widths), -waste)
        if best is None or score > best[0]:
            best = (score, ox, widths)
    assert best is not None
    _, ox, widths = best
    return {
        "offset": ox,
        "widths": widths,
        "ok": min(widths) + 1e-6 >= tile * min_frac,
        "min": min(widths),
        "n": len(widths),
    }


def layout_floor(room_w: float, room_d: float, tw: float, th: float, grout: float, pattern: str = "straight") -> dict[str, Any]:
    if pattern == "diagonal":
        # bounding along 45°: use axis-aligned cover with rotated size
        diag = math.hypot(tw, th) / math.sqrt(2)
        tw_use, th_use = diag, diag
        gx = _cover_1d(room_w, tw_use, grout)
        gy = _cover_1d(room_d, th_use, grout)
        tiles = _grid_tiles(gx, gy, tw_use, th_use, grout, rotate=45)
        tiles = [t for t in tiles if t["w"] > 0.02 and t["h"] > 0.02]
        return _pack("diagonal", tw, th, grout, gx, gy, tiles, extra="斜铺 45°，损耗按 10～15% 计")
    if pattern == "brick":
        gx = _cover_1d(room_w, tw, grout)
        gy = _cover_1d(room_d, th, grout)
        tiles = []
        y = gy["offset"]
        row = 0
        for h in gy["widths"]:
            shift = (tw + grout) / 3 if row % 2 else 0.0
            x = gx["offset"] - shift
            while x < room_w - 1e-9:
                x0, x1 = max(0.0, x), min(room_w, x + tw)
                y0, y1 = max(0.0, y), min(room_d, y + h)
                if x1 > x0 and y1 > y0:
                    tiles.append(_tile(x0, y0, x1 - x0, y1 - y0, tw, th))
                x += tw + grout
            y += h + grout
            row += 1
        return _pack("brick", tw, th, grout, gx, gy, tiles, extra="工字/1/3 错缝")
    gx = _cover_1d(room_w, tw, grout)
    gy = _cover_1d(room_d, th, grout)
    tiles = _grid_tiles(gx, gy, tw, th, grout, rotate=0)
    return _pack("straight", tw, th, grout, gx, gy, tiles, extra="正铺十字缝")


def _grid_tiles(gx, gy, tw, th, grout, rotate=0):
    tiles = []
    y = gy["offset"]
    for h in gy["widths"]:
        x = gx["offset"]
        for w in gx["widths"]:
            x0, y0 = max(0.0, x), max(0.0, y)
            tiles.append(_tile(x0, y0, w, h, tw, th, rotate))
            x += w + grout
        y += h + grout
    return tiles


def _tile(x, y, w, h, tw, th, rotate=0):
    full = abs(w - tw) < 0.004 and abs(h - th) < 0.004
    return {"x": x, "y": y, "w": w, "h": h, "full": full, "cut": not full, "rotate": rotate}


def _pack(pattern, tw, th, grout, gx, gy, tiles, extra=""):
    n = len(tiles)
    cuts = sum(1 for t in tiles if t["cut"])
    area = sum(t["w"] * t["h"] for t in tiles)
    piece = tw * th
    waste = max(0.0, n * piece - area)
    min_edge = min((min(t["w"], t["h"]) for t in tiles), default=0)
    return {
        "pattern": pattern,
        "tiles": tiles,
        "count": n,
        "cuts": cuts,
        "full": n - cuts,
        "area": round(area, 3),
        "waste_m2": round(waste, 3),
        "grout": grout,
        "tile_w": tw,
        "tile_h": th,
        "gx": gx,
        "gy": gy,
        "min_edge": round(min_edge, 3),
        "note": extra,
    }


def layout_wall(wall_len: float, wall_h: float, tw: float, th: float, grout: float, holes: list[dict] | None = None) -> dict[str, Any]:
    """Wall tiles: horizontal tw along length, th as course height (often 300x600 laid as 600 high)."""
    # Use th as vertical module (brick height), tw as width
    gx = _cover_1d(wall_len, tw, grout)
    gy = _cover_1d(wall_h, th, grout)
    tiles = _grid_tiles(gx, gy, tw, th, grout)
    holes = holes or []
    kept = []
    for t in tiles:
        cx, cy = t["x"] + t["w"] / 2, t["y"] + t["h"] / 2
        hit = False
        for h in holes:
            if h["x"] <= cx <= h["x"] + h["w"] and h["y"] <= cy <= h["y"] + h["h"]:
                hit = True
                break
        if not hit:
            kept.append(t)
    pack = _pack("wall", tw, th, grout, gx, gy, kept, extra="非整砖放阴角；门窗洞口单独收口")
    pack["holes"] = holes
    pack["wall_len"] = wall_len
    pack["wall_h"] = wall_h
    return pack
