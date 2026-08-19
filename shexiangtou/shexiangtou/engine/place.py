from __future__ import annotations

import html
import json
import math
import zipfile
from pathlib import Path
from typing import Any

import ezdxf

from shexiangtou.config import DATA_DIR, ensure_dirs
from shexiangtou.engine.parse import Door, Scene, load_catalog, parse_description, parse_dxf_bytes, parse_pdf_bytes


def _num(params: dict[str, Any], *keys: str, default: float = 0.0) -> float:
    for key in keys:
        if key not in params or params[key] in (None, ""):
            continue
        try:
            value = float(params[key])
        except (TypeError, ValueError):
            continue
        if value:
            return value
    return default


def _text(params: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = params.get(key)
        if value not in (None, ""):
            return str(value)
    return default


def parse_input(text: str = "", filename: str = "", file_bytes: bytes | None = None) -> Scene:
    name = (filename or "").lower()
    if file_bytes and name.endswith(".dxf"):
        return parse_dxf_bytes(file_bytes)
    if file_bytes and name.endswith(".pdf"):
        return parse_pdf_bytes(file_bytes)
    if (text or "").strip():
        return parse_description(text)
    return parse_description("办公室 12x8 层高3.0 2个门")


def layout_cameras(params: dict[str, Any], file_bytes: bytes | None = None, filename: str = "") -> dict[str, Any]:
    try:
        return _layout(params or {}, file_bytes, filename)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "svg": "", "n": 0, "cameras": [], "checks": []}


def _pick_camera(cat: dict[str, Any], spec: dict[str, Any], role: str, outdoor: bool) -> dict[str, Any]:
    prefer = list(spec.get("kinds") or [])
    if role == "入口":
        prefer = ["人脸", "筒型", "半球"] + prefer
    if outdoor:
        prefer = ["枪机", "球机"] + prefer
    cams = [c for c in cat["cameras"] if c["kind"] != ""]
    if outdoor:
        pool = [c for c in cams if not c["indoor"]] or cams
    else:
        pool = [c for c in cams if c["indoor"]] or cams
    ranked = sorted(
        pool,
        key=lambda c: (
            0 if c["kind"] in prefer else 1,
            0 if role != "入口" or c["kind"] == "人脸" else 1,
            -c["recognize"],
            c["W"],
        ),
    )
    return ranked[0]


def _radius(cam: dict[str, Any], purpose: str) -> float:
    key = {"辨认": "identify", "识别": "recognize", "观察": "observe", "监视": "detect"}.get(purpose, "observe")
    return max(2.0, float(cam.get(key) or cam["observe"]))


def _ang_diff(a: float, b: float) -> float:
    d = (a - b + math.pi) % (2 * math.pi) - math.pi
    return d


def _covers(cam_pt: dict[str, Any], px: float, py: float, radius: float, hfov: float) -> bool:
    dx, dy = px - cam_pt["x"], py - cam_pt["y"]
    dist = math.hypot(dx, dy)
    if dist <= 0.35:
        return True
    if dist > radius:
        return False
    heading = cam_pt["heading"]
    ang = math.atan2(dy, dx)
    half = math.radians(hfov) / 2 * 0.95
    if hfov >= 300:
        return True
    return abs(_ang_diff(ang, heading)) <= half


def _sample_points(w: float, d: float, step: float = 1.0) -> list[tuple[float, float]]:
    pts = []
    nx = max(2, int(w / step) + 1)
    ny = max(2, int(d / step) + 1)
    for i in range(nx):
        for j in range(ny):
            x = (i + 0.5) * w / nx
            y = (j + 0.5) * d / ny
            pts.append((x, y))
    return pts


def _snap_wall(x: float, y: float, w: float, d: float, inset: float = 0.22) -> tuple[float, float, float]:
    candidates = [
        (inset, min(max(y, inset), d - inset), 0.0),
        (w - inset, min(max(y, inset), d - inset), math.pi),
        (min(max(x, inset), w - inset), inset, math.pi / 2),
        (min(max(x, inset), w - inset), d - inset, -math.pi / 2),
    ]
    best = min(candidates, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2)
    sx, sy, _wall = best
    heading = math.atan2(d / 2 - sy, w / 2 - sx)
    return sx, sy, heading


def _uncovered(samples: list[tuple[float, float]], placed: list[dict[str, Any]]) -> list[tuple[float, float]]:
    miss = []
    for px, py in samples:
        ok = False
        for cam in placed:
            if _covers(cam, px, py, cam["radius"], cam["hfov"]):
                ok = True
                break
        if not ok:
            miss.append((px, py))
    return miss


def _layout(params: dict[str, Any], file_bytes: bytes | None, filename: str) -> dict[str, Any]:
    ensure_dirs()
    cat = load_catalog()
    scene = parse_input(_text(params, "description", "text"), filename, file_bytes)
    if w := _num(params, "width_m", "width"):
        scene.width = w
    if d := _num(params, "depth_m", "depth"):
        scene.depth = d
    if h := _num(params, "height_m", "height"):
        scene.height = h
    space = _text(params, "space_type", "room_type")
    if space:
        scene.name = space
    spec = next((s for s in cat["spaces"] if s["id"] == scene.name), cat["spaces"][0])
    scene.name = spec["id"]
    scene.indoor = bool(spec["indoor"])
    purpose = _text(params, "purpose") or scene.purpose or spec["purpose"]
    from shexiangtou.engine.parse import _default_doors

    nd = int(_num(params, "doors", default=0) or 0)
    scene.doors = [
        door
        for door in scene.doors
        if -0.2 <= door.x <= scene.width + 0.2 and -0.2 <= door.y <= scene.depth + 0.2
    ]
    if nd:
        scene.doors = _default_doors(scene.width, scene.depth, nd)
    if not scene.doors and spec["id"] not in ("周界", "室外场地"):
        scene.doors = _default_doors(scene.width, scene.depth, 1)

    outdoor = not scene.indoor
    area_cam = _pick_camera(cat, spec, "区域", outdoor)
    entry_cam = _pick_camera(cat, spec, "入口", outdoor)
    r_area = _radius(area_cam, purpose)
    r_entry = _radius(entry_cam, "辨认" if purpose in ("辨认", "识别") else purpose)
    mount_h = float(spec["mount_h"])
    if scene.height < mount_h + 0.2:
        mount_h = max(2.2, scene.height - 0.3)

    placed: list[dict[str, Any]] = []
    used = 1
    for door in scene.doors:
        inward = door.heading
        px = door.x + 0.45 * math.cos(inward)
        py = door.y + 0.45 * math.sin(inward)
        side = inward + math.pi / 2
        px += 0.35 * math.cos(side)
        py += 0.35 * math.sin(side)
        px = min(max(px, 0.2), scene.width - 0.2)
        py = min(max(py, 0.2), scene.depth - 0.2)
        heading = math.atan2(door.y - py, door.x - px)
        placed.append(
            _cam_rec(
                f"C{used:02d}",
                entry_cam,
                px,
                py,
                heading,
                mount_h if entry_cam["kind"] != "枪机" else max(mount_h, 2.8),
                r_entry,
                "入口/人脸",
                door,
            )
        )
        used += 1

    samples = _sample_points(scene.width, scene.depth, 1.0)
    # Seed corners looking inward for rooms that still have holes
    corners = [
        (0.22, 0.22),
        (scene.width - 0.22, 0.22),
        (0.22, scene.depth - 0.22),
        (scene.width - 0.22, scene.depth - 0.22),
    ]
    miss = _uncovered(samples, placed)
    if spec["id"] == "走廊" or (min(scene.width, scene.depth) <= 3.2 and max(scene.width, scene.depth) >= 8):
        long_x = scene.width >= scene.depth
        length = scene.width if long_x else scene.depth
        span = scene.depth if long_x else scene.width
        spacing = max(3.2, r_area * 0.9)
        n_along = max(2, math.ceil(length / spacing))
        for i in range(n_along):
            t = (i + 0.5) / n_along
            if long_x:
                x = t * scene.width
                y = 0.22 if i % 2 == 0 else max(0.22, span - 0.22)
                heading = 0.0 if x < scene.width / 2 else math.pi
            else:
                y = t * scene.depth
                x = 0.22 if i % 2 == 0 else max(0.22, span - 0.22)
                heading = math.pi / 2 if y < scene.depth / 2 else -math.pi / 2
            if any(math.hypot(x - p["x"], y - p["y"]) < 1.0 for p in placed):
                continue
            placed.append(_cam_rec(f"C{used:02d}", area_cam, x, y, heading, mount_h, r_area, "通道", None))
            used += 1
    else:
        # Add opposite corners until coverage or 2 cameras
        for cx, cy in corners:
            if any(math.hypot(cx - p["x"], cy - p["y"]) < 1.5 for p in placed):
                continue
            miss = _uncovered(samples, placed)
            if len(miss) / max(len(samples), 1) <= 0.05:
                break
            heading = math.atan2(scene.depth / 2 - cy, scene.width / 2 - cx)
            placed.append(_cam_rec(f"C{used:02d}", area_cam, cx, cy, heading, mount_h, r_area, "区域", None))
            used += 1
            if used > 2 + len(scene.doors):
                break

    # Greedy fill remaining blind spots, snap to walls
    for _ in range(36):
        miss = _uncovered(samples, placed)
        ratio = len(miss) / max(len(samples), 1)
        if ratio <= 0.04:
            break

        def score(pt: tuple[float, float]) -> float:
            if not placed:
                return 0
            return min(math.hypot(pt[0] - p["x"], pt[1] - p["y"]) for p in placed)

        target = max(miss, key=score)
        sx, sy, heading = _snap_wall(target[0], target[1], scene.width, scene.depth)
        heading = math.atan2(target[1] - sy, target[0] - sx)
        if any(math.hypot(sx - p["x"], sy - p["y"]) < 0.9 for p in placed):
            continue
        placed.append(_cam_rec(f"C{used:02d}", area_cam, sx, sy, heading, mount_h, r_area, "补盲", None))
        used += 1

    miss = _uncovered(samples, placed)
    cover = 1.0 - len(miss) / max(len(samples), 1)
    checks = _checks(scene, spec, placed, cover, purpose, outdoor)
    svg = _svg(scene, placed, miss)
    out = DATA_DIR / "latest"
    out.mkdir(parents=True, exist_ok=True)
    (out / "layout.svg").write_text(svg, encoding="utf-8")
    _dxf(scene, placed, out / "layout.dxf")

    qty_map: dict[str, dict[str, Any]] = {}
    for p in placed:
        key = p["camera"]["id"]
        row = qty_map.setdefault(key, {"name": p["camera"]["name"], "qty": 0, "unit": "台", "id": key})
        row["qty"] += 1
    qty = list(qty_map.values())
    nvr_ch = 8 if len(placed) <= 8 else (16 if len(placed) <= 16 else 32)
    qty.append({"name": f"硬盘录像机 {nvr_ch} 路", "qty": 1, "unit": "台", "id": "NVR"})
    poe = 8 if len(placed) <= 8 else (16 if len(placed) <= 16 else 24)
    qty.append({"name": f"PoE 交换机 {poe} 口", "qty": 1, "unit": "台", "id": "POE"})

    cameras_out = [
        {
            "id": p["id"],
            "x": round(p["x"], 2),
            "y": round(p["y"], 2),
            "heading_deg": round(math.degrees(p["heading"]) % 360, 1),
            "height_m": p["height"],
            "role": p["role"],
            "radius_m": p["radius"],
            "camera": {
                "id": p["camera"]["id"],
                "name": p["camera"]["name"],
                "kind": p["camera"]["kind"],
                "mp": p["camera"]["mp"],
                "lens_mm": p["camera"]["lens_mm"],
                "hfov": p["camera"]["hfov"],
                "P": p["camera"]["W"],
                "ip": p["camera"]["ip"],
                "mount": p["camera"]["mount"],
            },
        }
        for p in placed
    ]
    report = {
        "ok": True,
        "n": len(placed),
        "cover": round(cover * 100, 1),
        "purpose": purpose,
        "cameras": cameras_out,
        "qty": qty,
        "room": {
            "name": scene.name,
            "space_type": scene.name,
            "width_m": scene.width,
            "depth_m": scene.depth,
            "height_m": scene.height,
            "source": scene.source,
            "indoor": scene.indoor,
            "doors": len(scene.doors),
        },
        "checks": checks,
        "pass": all(c["ok"] for c in checks if c.get("hard")),
        "notes": [
            "点位按 GB 50348 / GB 50198 思路：出入口必看、通道衔接、壁装朝向室内，覆盖按 DORI（监视/观察/识别/辨认）半径校核。",
            "镜头与机型按场所推荐：室内半球/筒型，出入口人脸抓拍，室外枪机/球机。",
            "CAD 读取闭合房间轮廓及 0.7–2.6 m 短线作为门。本工具是布置建议，不能替代安防专项设计与现场复测。",
        ],
        "svg": svg,
        "warnings": [c["detail"] for c in checks if not c["ok"]],
    }
    (out / "report.json").write_text(
        json.dumps({k: v for k, v in report.items() if k != "svg"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    zip_path = DATA_DIR / "摄像头布置.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out / "layout.svg", "layout.svg")
        zf.write(out / "layout.dxf", "layout.dxf")
        zf.write(out / "report.json", "report.json")
    report["zip"] = str(zip_path)
    return report


def _more_doors(scene: Scene, n: int) -> list[Door]:
    from shexiangtou.engine.parse import _default_doors

    extra = _default_doors(scene.width, scene.depth, n + len(scene.doors))
    return extra[-n:]


def _cam_rec(cid, cam, x, y, heading, height, radius, role, door) -> dict[str, Any]:
    return {
        "id": cid,
        "camera": cam,
        "x": x,
        "y": y,
        "heading": heading,
        "height": round(height, 2),
        "radius": radius,
        "hfov": cam["hfov"],
        "role": role,
        "door": None if not door else {"x": door.x, "y": door.y},
    }


def _checks(scene: Scene, spec: dict, placed: list, cover: float, purpose: str, outdoor: bool) -> list[dict[str, Any]]:
    has_entry = any(p["role"].startswith("入口") for p in placed) or spec["id"] in ("周界", "室外场地", "停车场")
    kinds_ok = True
    if outdoor:
        kinds_ok = all(not p["camera"]["indoor"] or p["camera"]["kind"] in ("枪机", "球机") for p in placed)
    else:
        kinds_ok = all(p["camera"]["indoor"] or p["camera"]["kind"] in ("枪机", "球机") for p in placed)
    height_ok = all(1.8 <= p["height"] <= max(scene.height - 0.1, 2.0) + 2.5 for p in placed)
    return [
        {
            "name": "出入口覆盖",
            "ok": has_entry,
            "hard": True,
            "detail": "出入口已布置抓拍/迎面摄像机" if has_entry else "未识别到出入口摄像机",
        },
        {
            "name": "区域覆盖率",
            "ok": cover >= 0.95,
            "hard": True,
            "detail": f"抽点覆盖 {cover*100:.1f}%（目标 ≥95%，按 {purpose} 距离）",
        },
        {
            "name": "摄像机选型",
            "ok": kinds_ok,
            "hard": True,
            "detail": "室外场所使用枪机/球机" if outdoor else "室内场所使用半球/筒型/人脸/鱼眼",
        },
        {
            "name": "安装高度",
            "ok": height_ok,
            "hard": False,
            "detail": f"安装高度约 {placed[0]['height'] if placed else '-'} m，层高 {scene.height} m",
        },
        {
            "name": "GB 50348",
            "ok": True,
            "hard": False,
            "detail": f"按 {purpose} 等级选用 DORI 半径，须结合现场光照、逆光与遮挡复核",
        },
    ]


def _svg(scene: Scene, placed: list[dict[str, Any]], miss: list[tuple[float, float]]) -> str:
    pad = 56
    scale = 560 / max(scene.width, 0.5)
    bw = pad * 2 + scene.width * scale
    bh = pad * 2 + scene.depth * scale + 36

    def px(x, y):
        return pad + x * scale, pad + 28 + (scene.depth - y) * scale

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw:.0f}" height="{bh:.0f}" viewBox="0 0 {bw:.0f} {bh:.0f}">',
        '<rect width="100%" height="100%" fill="#f4f7fb"/>',
        f'<text x="{bw/2:.0f}" y="22" text-anchor="middle" font-size="15" fill="#1b4f8a" font-family="Microsoft YaHei, sans-serif">'
        f'{html.escape(scene.name)} 摄像头布置  {len(placed)} 台</text>',
    ]
    x0, y0 = px(0, scene.depth)
    parts.append(
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{scene.width*scale:.1f}" height="{scene.depth*scale:.1f}" fill="#fff" stroke="#12365f" stroke-width="2"/>'
    )
    for door in scene.doors:
        dx, dy = px(door.x, door.y)
        parts.append(f'<rect x="{dx-8:.1f}" y="{dy-4:.1f}" width="16" height="8" fill="#f97316" stroke="#7c2d12"/>')
        parts.append(f'<text x="{dx:.1f}" y="{dy-8:.1f}" font-size="9" text-anchor="middle" fill="#9a3412">门</text>')
    for p in placed:
        cx, cy = px(p["x"], p["y"])
        reach = p["radius"] * scale
        half = math.radians(p["hfov"]) / 2
        hdg = p["heading"]
        # FOV wedge
        if p["hfov"] >= 300:
            parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{min(reach, 80):.1f}" fill="#93c5fd" fill-opacity="0.18" stroke="#3b82f6" stroke-dasharray="4 3"/>')
        else:
            a1 = -hdg - half
            a2 = -hdg + half
            # SVG y is flipped already via px(); heading in world +x=east +y=north, screen y down
            def sxy(ang, r):
                # world: x+=cos, y+=sin; screen uses px()
                wx = p["x"] + r * math.cos(ang)
                wy = p["y"] + r * math.sin(ang)
                return px(wx, wy)

            p1 = sxy(hdg - half, p["radius"])
            p2 = sxy(hdg + half, p["radius"])
            parts.append(
                f'<path d="M {cx:.1f} {cy:.1f} L {p1[0]:.1f} {p1[1]:.1f} A {reach:.1f} {reach:.1f} 0 0 0 {p2[0]:.1f} {p2[1]:.1f} Z" fill="#93c5fd" fill-opacity="0.22" stroke="#2563eb" stroke-width="0.8"/>'
            )
        fill = "#dc2626" if p["role"].startswith("入口") else "#1d4ed8"
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="7" fill="{fill}" stroke="#111"/>')
        parts.append(
            f'<text x="{cx:.1f}" y="{cy+16:.1f}" font-size="10" text-anchor="middle" fill="#1e3a5f">{p["id"]} {html.escape(p["camera"]["kind"])}</text>'
        )
    parts.append(
        f'<text x="{pad + scene.width*scale/2:.0f}" y="{bh-10:.0f}" text-anchor="middle" font-size="11" fill="#334155">'
        f'{scene.width}×{scene.depth}×{scene.height}m  {len(placed)}台  覆盖目标抽点</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _dxf(scene: Scene, placed: list[dict[str, Any]], path: Path) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6
    for layer, color in (("ROOM", 7), ("DOOR", 30), ("CAMERA", 1), ("FOV", 5)):
        if layer not in doc.layers:
            doc.layers.add(layer, color=color)
    msp = doc.modelspace()
    k = 1000
    msp.add_lwpolyline(
        [(0, 0), (scene.width * k, 0), (scene.width * k, scene.depth * k), (0, scene.depth * k)],
        close=True,
        dxfattribs={"layer": "ROOM"},
    )
    for door in scene.doors:
        msp.add_circle((door.x * k, door.y * k), 120, dxfattribs={"layer": "DOOR"})
    for p in placed:
        msp.add_circle((p["x"] * k, p["y"] * k), 150, dxfattribs={"layer": "CAMERA"})
        ex = p["x"] + 1.2 * math.cos(p["heading"])
        ey = p["y"] + 1.2 * math.sin(p["heading"])
        msp.add_line((p["x"] * k, p["y"] * k), (ex * k, ey * k), dxfattribs={"layer": "FOV"})
    doc.saveas(path)
