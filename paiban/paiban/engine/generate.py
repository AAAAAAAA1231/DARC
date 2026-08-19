from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

import ezdxf

from paiban.config import DATA_DIR, ensure_dirs
from paiban.engine.ceiling import layout_ceiling
from paiban.engine.draw import svg_ceiling, svg_floor, svg_furniture, svg_walls
from paiban.engine.furniture import layout_furniture
from paiban.engine.parse import Room, load_catalog, parse_description, parse_dxf_bytes, parse_pdf_bytes
from paiban.engine.rules import check_ceiling, check_floor, check_wall, quantities
from paiban.engine.tiles import layout_floor, layout_wall


def parse_input(text: str = "", filename: str = "", file_bytes: bytes | None = None) -> dict[str, Any]:
    name = (filename or "").lower()
    if file_bytes and name.endswith(".dxf"):
        return parse_dxf_bytes(file_bytes)
    if file_bytes and name.endswith(".pdf"):
        return parse_pdf_bytes(file_bytes)
    if file_bytes and name.endswith(".txt"):
        return parse_description(file_bytes.decode("utf-8", errors="ignore"))
    return parse_description(text or "客厅 4.8x6.2 层高2.8 地砖 800x800")


def generate_layout(params: dict[str, Any], file_bytes: bytes | None = None, filename: str = "") -> dict[str, Any]:
    ensure_dirs()
    parsed = parse_input(params.get("text") or "", filename, file_bytes)
    cat = load_catalog()
    room: Room = parsed["room"]
    if params.get("width"):
        room.width = float(params["width"])
    if params.get("depth"):
        room.depth = float(params["depth"])
    if params.get("height"):
        room.height = float(params["height"])
    if params.get("room_kind"):
        room.kind = params["room_kind"]
        room.name = params.get("room_name") or params["room_kind"]
    task = params.get("task") or parsed["task"]
    pattern = params.get("pattern") or parsed["pattern"]
    floor_tile = _pick(cat["tile_floors"], params.get("floor_tile"), parsed["floor_tile"])
    wall_tile = _pick(cat["tile_walls"], params.get("wall_tile"), parsed["wall_tile"])
    ceiling_spec = _pick(cat["ceilings"], params.get("ceiling"), parsed["ceiling"])

    svg = ""
    payload: Any
    checks: list
    if task == "wall":
        walls = _all_walls(room, wall_tile)
        payload = walls
        checks = check_wall(room, wall_tile, walls)
        svg = svg_walls(room, walls)
        qty = quantities("wall", room, walls, tile=wall_tile)
    elif task == "ceiling":
        payload = layout_ceiling(room.width, room.depth, ceiling_spec)
        checks = check_ceiling(room, payload)
        svg = svg_ceiling(room, payload)
        qty = quantities("ceiling", room, payload, ceil=ceiling_spec)
    elif task == "furniture":
        payload = layout_furniture(room.width, room.depth, room.kind, cat)
        checks = payload["checks"]
        svg = svg_furniture(room, payload)
        qty = quantities("furniture", room, payload)
    else:
        task = "floor"
        payload = layout_floor(room.width, room.depth, floor_tile["w"], floor_tile["h"], floor_tile["grout"], pattern)
        checks = check_floor(room, floor_tile, payload)
        svg = svg_floor(room, payload)
        qty = quantities("floor", room, payload, tile=floor_tile)

    out = DATA_DIR / "latest"
    out.mkdir(parents=True, exist_ok=True)
    (out / "layout.svg").write_text(svg, encoding="utf-8")
    _to_dxf(room, task, payload, out / "layout.dxf")
    report = {
        "room": {"name": room.name, "kind": room.kind, "width": room.width, "depth": room.depth, "height": room.height, "area": round(room.area, 2), "source": room.source},
        "task": task,
        "pattern": pattern,
        "floor_tile": floor_tile,
        "wall_tile": wall_tile,
        "ceiling": ceiling_spec,
        "checks": checks,
        "qty": qty,
        "codes": cat["codes"],
        "pass": all(bool(c.get("ok")) for c in checks),
        "warnings": [c["msg"] for c in checks if not c["ok"]],
        "parsed_from": parsed.get("cad_rooms") or parsed.get("pdf_text", "")[:80] or parsed.get("text", "")[:80],
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = DATA_DIR / "装修排版.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out / "layout.svg", "layout.svg")
        zf.write(out / "layout.dxf", "layout.dxf")
        zf.write(out / "report.json", "report.json")
    report["svg"] = svg
    report["zip"] = str(zip_path)
    report["summary"] = _summary(task, payload)
    return report


def _pick(items: list[dict], name: str | None, fallback: dict) -> dict:
    if name:
        for it in items:
            if it["name"] == name:
                return it
    return fallback


def _all_walls(room: Room, tile: dict) -> list[dict]:
    tw, th, g = tile["w"], tile["h"], tile["grout"]
    walls_meta = [
        ("南墙（开门）", room.width, [{"x": o.offset, "y": 0.0, "w": o.width, "h": min(o.height, room.height)} for o in room.openings if o.wall == "S"]),
        ("北墙", room.width, []),
        ("西墙", room.depth, []),
        ("东墙", room.depth, []),
    ]
    out = []
    for name, length, holes in walls_meta:
        lay = layout_wall(length, room.height, tw, th, g, holes)
        lay["name"] = name
        out.append(lay)
    return out


def _summary(task: str, payload: Any) -> dict[str, Any]:
    if task == "floor":
        return {"count": payload["count"], "cuts": payload["cuts"], "min_edge_mm": int(payload["min_edge"] * 1000)}
    if task == "wall":
        return {"count": sum(w["count"] for w in payload), "cuts": sum(w["cuts"] for w in payload)}
    if task == "ceiling":
        return {"panels": payload["panel_count"], "hangers": payload["hanger_count"], "main_m": payload["main_spacing"]}
    return {"items": len(payload.get("items") or [])}


def _to_dxf(room: Room, task: str, payload: Any, path: Path) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6  # meters
    msp = doc.modelspace()
    k = 1000  # mm
    msp.add_lwpolyline([(0, 0), (room.width * k, 0), (room.width * k, room.depth * k), (0, room.depth * k)], close=True, dxfattribs={"layer": "ROOM"})
    if task == "floor":
        for t in payload["tiles"]:
            x, y, w, h = t["x"] * k, t["y"] * k, t["w"] * k, t["h"] * k
            msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": "TILE"})
    elif task == "ceiling":
        for pan in payload["panels"]:
            x, y, w, h = pan["x"] * k, pan["y"] * k, pan["w"] * k, pan["h"] * k
            msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], close=True, dxfattribs={"layer": "PANEL"})
        for ln in payload["mains"] + payload["seconds"]:
            msp.add_line((ln["x1"] * k, ln["y1"] * k), (ln["x2"] * k, ln["y2"] * k), dxfattribs={"layer": "KEEL"})
    elif task == "furniture":
        for it in payload["items"]:
            x, y, w, d = it["x"] * k, it["y"] * k, it["w"] * k, it["d"] * k
            msp.add_lwpolyline([(x, y), (x + w, y), (x + w, y + d), (x, y + d)], close=True, dxfattribs={"layer": "FURN"})
            msp.add_text(it["name"], dxfattribs={"height": 80}).set_placement((x + 20, y + 20))
    elif task == "wall":
        yoff = 0.0
        for w in payload:
            for t in w["tiles"]:
                x, y, tw, th = t["x"] * k, (yoff + t["y"]) * k, t["w"] * k, t["h"] * k
                msp.add_lwpolyline([(x, y), (x + tw, y), (x + tw, y + th), (x, y + th)], close=True, dxfattribs={"layer": "TILE"})
            yoff += w["wall_h"] + 0.4
    doc.saveas(path)
