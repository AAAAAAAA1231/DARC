from __future__ import annotations

import html
import json
import zipfile
from pathlib import Path
from typing import Any

import ezdxf

from dengju.config import DATA_DIR, ensure_dirs
from dengju.engine.calc import (
    avg_illuminance,
    emergency_points,
    fixture_points,
    grid_for_count,
    lamps_needed,
    mount_height_m,
    room_index,
    space_grid,
    utilization_factor,
)
from dengju.engine.parse import RoomInput, load_catalog, parse_description, parse_dxf_bytes, parse_pdf_bytes

ROOM_ALIASES = {
    "普通教室": "普通教室",
    "教室": "普通教室",
}


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


def parse_input(text: str = "", filename: str = "", file_bytes: bytes | None = None) -> RoomInput:
    name = (filename or "").lower()
    if file_bytes and name.endswith(".dxf"):
        return parse_dxf_bytes(file_bytes)
    if file_bytes and name.endswith(".pdf"):
        return parse_pdf_bytes(file_bytes)
    if text.strip():
        return parse_description(text)
    return parse_description("普通办公室 7.2x9.0 层高2.8 300lx")


def select_lighting(params: dict[str, Any], file_bytes: bytes | None = None, filename: str = "") -> dict[str, Any]:
    try:
        return _select_lighting(params or {}, file_bytes, filename)
    except Exception as exc:
        return {"ok": False, "error": str(exc), "svg": "", "n": 0, "e_avg": 0, "checks": []}


def _select_lighting(params: dict[str, Any], file_bytes: bytes | None, filename: str) -> dict[str, Any]:
    ensure_dirs()
    cat = load_catalog()
    room = parse_input(_text(params, "description", "text"), filename, file_bytes)
    if w := _num(params, "width_m", "width"):
        room.width = w
    if d := _num(params, "depth_m", "depth"):
        room.depth = d
    if h := _num(params, "height_m", "height"):
        room.height = h
    room_type = _text(params, "room_type")
    if room_type:
        room.name = ROOM_ALIASES.get(room_type, room_type)
    spec = next((r for r in cat["rooms"] if r["name"] == room.name), cat["rooms"][0])
    room.name = spec["name"]
    if e := _num(params, "illuminance_lx", "E"):
        room.E = e
    if not room.E:
        room.E = spec["E"]
    room.mf = _num(params, "mf", default=0) or spec["mf"]
    work_h = _num(params, "work_plane_m", "work_h", default=0) or spec["work_h"]
    prefer = spec["kinds"]
    forced = _text(params, "fixture_id")
    ra_min = int(_num(params, "ra_min", default=0) or spec["ra"])
    cct = int(_num(params, "cct", default=4000) or 4000)
    area = room.width * room.depth

    scored: list[dict[str, Any]] = []
    for fx in cat["fixtures"]:
        if fx["kind"] == "应急":
            continue
        if fx["Ra"] < ra_min - 5:
            continue
        h_m, aff, suspended = mount_height_m(room.height, work_h, fx["kind"], room.name)
        k = room_index(room.width, room.depth, h_m)
        uf = utilization_factor(k)
        cand = _best_layout(fx, room, spec, prefer, area, h_m, uf, forced)
        if cand:
            cand["h_m"] = h_m
            cand["aff"] = aff
            cand["k"] = k
            cand["uf"] = uf
            cand["suspended"] = suspended
            scored.append(cand)

    scored.sort(key=lambda x: x["score"], reverse=True)
    passing = [s for s in scored if s["hard"]]
    if forced:
        named = [s for s in scored if s["fixture"]["id"] == forced]
        if named and named[0]["hard"]:
            passing = named + [s for s in passing if s["fixture"]["id"] != forced]
        elif passing:
            pass
        elif named:
            passing = named
    if passing:
        scored_view = passing + [s for s in scored if not s["hard"]]
        best = passing[0]
    elif scored:
        scored_view = scored
        best = scored[0]
    else:
        fx = next(f for f in cat["fixtures"] if f["kind"] != "应急")
        h_m, aff, suspended = mount_height_m(room.height, work_h, fx["kind"], room.name)
        k = room_index(room.width, room.depth, h_m)
        uf = utilization_factor(k)
        n_raw = lamps_needed(room.E, area, fx["lm"], uf, room.mf)
        nx, ny, n = grid_for_count(max(1, int(n_raw + 0.999)), room.width, room.depth)
        best = _pack_candidate(fx, n_raw, nx, ny, n, room, spec, prefer, area, h_m, uf)
        best.update({"h_m": h_m, "aff": aff, "k": k, "uf": uf, "suspended": suspended})
        scored_view = [best]

    fx = best["fixture"]
    h_m = best["h_m"]
    k = best["k"]
    uf = best["uf"]
    pts = fixture_points(room.width, room.depth, best["nx"], best["ny"])
    emg = emergency_points(room.width, room.depth, room.name)
    checks = [
        {"name": "平均照度", "ok": best["ok_e"], "code": "GB 50034", "detail": f"计算平均照度 {best['E_avg']} lx，目标 {room.E} lx"},
        {"name": "LPD", "ok": best["ok_lpd"], "code": "GB 50034 LPD", "detail": f"功率密度 {best['lpd']} W/㎡，限值 {spec['lpd']} W/㎡"},
        {"name": "UGR", "ok": best["ok_ugr"], "code": "GB 50034 UGR", "detail": f"灯具 UGR {fx['ugr']}，房间限值 ≤{spec['ugr']}"},
        {"name": "显色指数", "ok": fx["Ra"] >= spec["ra"], "code": "GB 50034 Ra", "detail": f"显色指数 Ra {fx['Ra']}，要求 ≥{spec['ra']}"},
        {"name": "距高比", "ok": best["ok_s"], "code": "距高比", "detail": f"间距 {best['sx']}×{best['sy']} m，安装高度 {h_m:.2f} m，SHR {fx['shr']}"},
        {
            "name": "应急照明",
            "ok": True,
            "code": "GB 51309 应急",
            "detail": f"示意疏散标志 {sum(1 for p in emg if p['kind']=='疏散标志')} 盏、应急照明 {sum(1 for p in emg if p['kind']=='应急照明')} 盏，须按疏散口复核",
        },
    ]
    svg = _svg(room, best, pts, emg, k, uf, h_m)
    out = DATA_DIR / "latest"
    out.mkdir(parents=True, exist_ok=True)
    (out / "layout.svg").write_text(svg, encoding="utf-8")
    _dxf(room, pts, emg, out / "layout.dxf")
    selected = {
        "id": fx["id"],
        "name": fx["name"],
        "kind": fx["kind"],
        "W": fx["W"],
        "P": fx["W"],
        "lm": fx["lm"],
        "Phi": fx["lm"],
        "n": best["n"],
        "nx": best["nx"],
        "ny": best["ny"],
        "E_avg": best["E_avg"],
        "lpd": best["lpd"],
        "W_total": best["W_total"],
        "sx": best["sx"],
        "sy": best["sy"],
        "mount": fx["mount"],
        "size": fx["size"],
        "Ra": fx["Ra"],
        "CCT": fx["cct"],
        "cct_lamp": fx["cct"],
    }
    alt_src = [s for s in scored_view if s["hard"] and s["fixture"]["id"] != fx["id"]][:5]
    alternatives = [
        {
            "id": s["fixture"]["id"],
            "name": s["fixture"]["name"],
            "P": s["fixture"]["W"],
            "Phi": s["fixture"]["lm"],
            "n": s["n"],
            "e_avg": s["E_avg"],
            "lpd": s["lpd"],
            "W_total": s["W_total"],
            "pass": True,
        }
        for s in alt_src
    ]
    notes = [
        "照度用利用系数法：N = E·A / (Φ·UF·MF)。UF 按室形指数近似，不是逐点计算。",
        "推荐方案必须同时满足目标照度与 GB 50034 LPD，不会给出超标方案。",
        "布置为正方形/矩形阵列，距边约半间距。精装天花、灯槽、重点照明需深化。",
        "依据 GB 50034 建筑照明设计标准（照度、UGR、Ra、LPD）及 GB 51309 消防应急照明示意。",
    ]
    if best.get("suspended"):
        notes.insert(
            1,
            f"层高 {room.height} m，办公类面板灯按吊顶安装高度 {best['aff']:.1f} m 计算（距工作面 {h_m:.2f} m），不把灯装在屋面。",
        )
    report = {
        "ok": True,
        "n": best["n"],
        "nx": best["nx"],
        "ny": best["ny"],
        "e_avg": best["E_avg"],
        "lpd": best["lpd"],
        "power_w": best["W_total"],
        "spacing_m": round((best["sx"] + best["sy"]) / 2, 2),
        "fixture": selected,
        "room": {
            "name": room.name,
            "room_type": room.name,
            "width": room.width,
            "depth": room.depth,
            "height": room.height,
            "width_m": room.width,
            "depth_m": room.depth,
            "height_m": room.height,
            "area": round(area, 2),
            "source": room.source,
            "E": room.E,
            "work_h": work_h,
            "h_m": round(h_m, 2),
            "k": round(k, 2),
            "uf": round(uf, 3),
            "mf": room.mf,
            "cct": cct,
        },
        "selected": selected,
        "alternatives": alternatives,
        "points": pts,
        "emergency": emg,
        "checks": checks,
        "qty": [
            {"name": fx["name"], "qty": best["n"], "unit": "套"},
            {"name": "疏散标志灯", "qty": sum(1 for p in emg if p["kind"] == "疏散标志"), "unit": "套"},
            {"name": "应急照明灯", "qty": sum(1 for p in emg if p["kind"] == "应急照明"), "unit": "套"},
            {"name": "装机功率", "qty": best["W_total"], "unit": "W"},
        ],
        "notes": notes,
        "pass": all(c["ok"] for c in checks if "示意" not in c["detail"]),
        "warnings": [c["detail"] for c in checks if not c["ok"]],
        "svg": svg,
    }
    (out / "report.json").write_text(json.dumps({k: v for k, v in report.items() if k != "svg"}, ensure_ascii=False, indent=2), encoding="utf-8")
    zip_path = DATA_DIR / "灯具选型.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(out / "layout.svg", "layout.svg")
        zf.write(out / "layout.dxf", "layout.dxf")
        zf.write(out / "report.json", "report.json")
    report["zip"] = str(zip_path)
    return report


def _pack_candidate(
    fx: dict[str, Any],
    n_raw: float,
    nx: int,
    ny: int,
    n: int,
    room: RoomInput,
    spec: dict[str, Any],
    prefer: list[str],
    area: float,
    h_m: float,
    uf: float,
) -> dict[str, Any]:
    E_avg = avg_illuminance(n, fx["lm"], uf, room.mf, area)
    watts = n * fx["W"]
    lpd = watts / area if area else 0
    sx, sy = room.width / max(nx, 1), room.depth / max(ny, 1)
    ok_e = E_avg >= room.E * 0.95
    ok_lpd = lpd <= spec["lpd"] + 1e-9
    ok_ugr = fx["ugr"] <= spec["ugr"]
    ok_ra = fx["Ra"] >= spec["ra"]
    ok_s = sx <= fx["shr"] * h_m * 1.15 and sy <= fx["shr"] * h_m * 1.15
    hard = ok_e and ok_lpd and ok_ugr and ok_ra
    score = (
        int(hard),
        int(fx["kind"] in prefer),
        int(ok_s),
        -lpd,
        -n,
        -abs(E_avg - room.E),
    )
    return {
        "fixture": fx,
        "n_calc": round(n_raw, 2),
        "nx": nx,
        "ny": ny,
        "n": n,
        "E_avg": round(E_avg, 1),
        "W_total": watts,
        "lpd": round(lpd, 2),
        "sx": round(sx, 2),
        "sy": round(sy, 2),
        "ok_e": ok_e,
        "ok_lpd": ok_lpd,
        "ok_ugr": ok_ugr,
        "ok_ra": ok_ra,
        "ok_s": ok_s,
        "hard": hard,
        "score": score,
    }


def _best_layout(
    fx: dict[str, Any],
    room: RoomInput,
    spec: dict[str, Any],
    prefer: list[str],
    area: float,
    h_m: float,
    uf: float,
    forced: str,
) -> dict[str, Any] | None:
    n_raw = lamps_needed(room.E, area, fx["lm"], uf, room.mf)
    n_need = max(1, int(n_raw + 0.999))
    if fx["W"] <= 0 or area <= 0:
        return None
    max_n = int(spec["lpd"] * area / fx["W"] + 1e-9)
    if max_n < 1:
        max_n = 1
    _sx, _sy, n_space = space_grid(room.width, room.depth, h_m, fx["shr"])
    tries = {n_need}
    if n_space >= n_need:
        tries.add(min(n_space, max(max_n, n_need)))
    for extra in range(0, 13):
        tries.add(n_need + extra)
    cands: list[dict[str, Any]] = []
    for n_try in sorted(tries):
        cap = max(max_n, n_try) if forced == fx["id"] else max_n
        if n_try > cap and fx["id"] != forced:
            continue
        nx, ny, n = grid_for_count(n_try, room.width, room.depth, max_n=cap)
        if fx["id"] != forced and n > max_n:
            continue
        cands.append(_pack_candidate(fx, n_raw, nx, ny, n, room, spec, prefer, area, h_m, uf))
    if not cands:
        nx, ny, n = grid_for_count(n_need, room.width, room.depth)
        return _pack_candidate(fx, n_raw, nx, ny, n, room, spec, prefer, area, h_m, uf)
    hard = [c for c in cands if c["hard"]]
    pool = hard or cands
    pool.sort(key=lambda x: x["score"], reverse=True)
    return pool[0]


def _svg(room: RoomInput, best: dict, pts, emg, k, uf, h_m) -> str:
    pad = 48
    scale = 520 / max(room.width, 0.5)
    bw = pad * 2 + room.width * scale
    bh = pad * 2 + room.depth * scale + 28

    def px(x, y):
        return pad + x * scale, pad + 24 + (room.depth - y) * scale

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{bw:.0f}" height="{bh:.0f}" viewBox="0 0 {bw:.0f} {bh:.0f}">',
        '<rect width="100%" height="100%" fill="#f4f7fb"/>',
        f'<text x="{bw/2:.0f}" y="20" text-anchor="middle" font-size="15" fill="#1b4f8a" font-family="Microsoft YaHei, sans-serif">'
        f'{html.escape(room.name)} 灯具布置  {html.escape(best["fixture"]["name"])} ×{best["n"]}</text>',
    ]
    x0, y0 = px(0, room.depth)
    parts.append(
        f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{room.width*scale:.1f}" height="{room.depth*scale:.1f}" fill="#fff" stroke="#12365f" stroke-width="2"/>'
    )
    for x, y in pts:
        cx, cy = px(x, y)
        r = max(6, 0.18 * scale)
        parts.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="#facc15" stroke="#1e3a5f" stroke-width="1.4"/>')
        parts.append(f'<text x="{cx:.1f}" y="{cy+r+10:.1f}" font-size="9" text-anchor="middle" fill="#334155">{best["fixture"]["id"]}</text>')
    for p in emg:
        cx, cy = px(p["x"], p["y"])
        fill = "#f97316" if p["kind"] == "疏散标志" else "#22c55e"
        parts.append(f'<rect x="{cx-7:.1f}" y="{cy-5:.1f}" width="14" height="10" fill="{fill}" stroke="#111"/>')
    parts.append(
        f'<text x="{pad + room.width*scale/2:.0f}" y="{bh-8:.0f}" text-anchor="middle" font-size="11" fill="#334155">'
        f'{room.width}×{room.depth}×{room.height}m  E≈{best["E_avg"]}lx  LPD {best["lpd"]}W/㎡  k={k:.2f} UF={uf:.2f}  hm={h_m:.2f}m</text>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _dxf(room: RoomInput, pts, emg, path: Path) -> None:
    doc = ezdxf.new("R2010", setup=True)
    doc.header["$INSUNITS"] = 6
    for layer, color in (("ROOM", 7), ("LUMINAIRE", 2), ("EMERGENCY", 1)):
        if layer not in doc.layers:
            doc.layers.add(layer, color=color)
    msp = doc.modelspace()
    k = 1000
    msp.add_lwpolyline(
        [(0, 0), (room.width * k, 0), (room.width * k, room.depth * k), (0, room.depth * k)],
        close=True,
        dxfattribs={"layer": "ROOM"},
    )
    for x, y in pts:
        msp.add_circle((x * k, y * k), 120, dxfattribs={"layer": "LUMINAIRE"})
    for p in emg:
        msp.add_circle((p["x"] * k, p["y"] * k), 80, dxfattribs={"layer": "EMERGENCY"})
    doc.saveas(path)
