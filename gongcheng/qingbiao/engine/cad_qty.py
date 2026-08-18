from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from openpyxl import Workbook

SKIP_LAYER = re.compile(
    r"标注|尺寸|轴号|轴圈|图框|图签|视口|标题|defpoints|viewport|^dim|title.?block",
    re.I,
)

INSUNITS_TO_M = {
    0: None,  # unitless
    1: 0.0254,  # inches
    2: 0.3048,  # feet
    4: 0.001,  # mm
    5: 0.01,  # cm
    6: 1.0,  # m
    14: 1e-6,  # microns
}

UNIT_NAME = {0: "无单位", 1: "in", 2: "ft", 4: "mm", 5: "cm", 6: "m"}


def _unit_to_m(insunits: int, override: str | None) -> tuple[float, str]:
    if override:
        key = override.strip().lower()
        table = {"mm": 0.001, "毫米": 0.001, "cm": 0.01, "厘米": 0.01, "m": 1.0, "米": 1.0}
        if key not in table:
            raise ValueError("单位请填 mm / cm / m")
        return table[key], key
    factor = INSUNITS_TO_M.get(int(insunits), None)
    if factor is None:
        return 0.001, "mm(按毫米默认)"
    return factor, UNIT_NAME.get(int(insunits), str(insunits))


def _skip_layer(name: str, skip_annot: bool) -> bool:
    if not skip_annot:
        return False
    return bool(SKIP_LAYER.search(name or ""))


def _polyline_metrics(entity) -> tuple[float, float]:
    dxftype = entity.dxftype()
    if dxftype == "LINE":
        try:
            return float(entity.dxf.start.distance(entity.dxf.end)), 0.0
        except Exception:
            return 0.0, 0.0
    if dxftype == "CIRCLE":
        r = float(entity.dxf.radius)
        return 2 * 3.141592653589793 * r, 3.141592653589793 * r * r
    if dxftype == "ARC":
        try:
            return float(entity.length), 0.0
        except Exception:
            return 0.0, 0.0
    points = []
    closed = False
    try:
        if dxftype == "LWPOLYLINE":
            points = [(float(p[0]), float(p[1])) for p in entity.get_points("xy")]
            closed = bool(entity.closed)
        elif dxftype == "POLYLINE":
            points = [(float(v.dxf.location.x), float(v.dxf.location.y)) for v in entity.vertices]
            closed = bool(entity.is_closed)
    except Exception:
        points = []
    if len(points) < 2:
        path_obj = _safe_path(entity)
        if path_obj is None:
            return 0.0, 0.0
        try:
            length = float(path_obj.length())
        except Exception:
            length = 0.0
        area = 0.0
        try:
            if getattr(path_obj, "is_closed", False):
                area = abs(float(path_obj.area()))
        except Exception:
            pass
        return length, area
    length = 0.0
    for i in range(1, len(points)):
        x0, y0 = points[i - 1]
        x1, y1 = points[i]
        length += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    if closed and points[0] != points[-1]:
        x0, y0 = points[-1]
        x1, y1 = points[0]
        length += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
    area = 0.0
    if closed and len(points) >= 3:
        ring = points + [points[0]]
        acc = 0.0
        for i in range(len(ring) - 1):
            acc += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
        area = abs(acc) / 2.0
    return length, area


def _safe_path(entity) -> Any:
    try:
        from ezdxf.path import make_path

        return make_path(entity)
    except Exception:
        return None


def _hatch_area(entity) -> float:
    try:
        return abs(float(entity.area))
    except Exception:
        total = 0.0
        try:
            for p in entity.paths:
                sp = getattr(p, "rendering_path", None)
                if sp is None:
                    continue
                total += abs(float(sp.area()))
        except Exception:
            return 0.0
        return total


def analyze_dxf(
    path: Path,
    *,
    unit: str | None = None,
    skip_annot: bool = True,
    thicknesses: dict[str, float] | None = None,
) -> dict[str, Any]:
    suffix = path.suffix.lower()
    if suffix == ".dwg":
        raise ValueError(
            "本机不解析二进制 DWG。请用 AutoCAD / 中望 / 浩辰 / 天正将图纸【另存为 DXF】（建议 R2010 或 R2000）后再上传。"
            "天正自定义墙体请先炸开或导出为标准线段，否则长度会偏少。"
        )
    if suffix not in {".dxf"}:
        raise ValueError("请上传 .dxf 图纸（DWG 请先另存为 DXF）")

    import ezdxf
    from ezdxf import recover

    try:
        doc = ezdxf.readfile(str(path))
    except Exception:
        doc, auditor = recover.readfile(str(path))
        if auditor.has_errors and not doc:
            raise ValueError("DXF 无法读取，请另存为 R2010 ASCII DXF 后再试") from None

    insunits = int(doc.header.get("$INSUNITS", 0) or 0)
    factor, unit_label = _unit_to_m(insunits, unit)
    area_factor = factor * factor
    msp = doc.modelspace()

    layers: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "layer": "",
            "length_m": 0.0,
            "area_m2": 0.0,
            "count": 0,
            "entities": 0,
            "blocks": defaultdict(int),
        }
    )
    skipped = 0
    total_ent = 0
    for e in msp:
        total_ent += 1
        name = str(e.dxf.layer or "0")
        if _skip_layer(name, skip_annot):
            skipped += 1
            continue
        row = layers[name]
        row["layer"] = name
        dxftype = e.dxftype()
        if dxftype in {"TEXT", "MTEXT", "DIMENSION", "LEADER", "MULTILEADER", "ATTDEF", "ATTRIB", "VIEWPORT"}:
            skipped += 1
            continue
        if dxftype == "INSERT":
            bname = str(e.dxf.name or "块")
            row["blocks"][bname] += 1
            row["count"] += 1
            row["entities"] += 1
            continue
        if dxftype == "HATCH":
            row["area_m2"] += _hatch_area(e) * area_factor
            row["entities"] += 1
            continue
        length, area = _polyline_metrics(e)
        if length <= 0 and area <= 0:
            continue
        row["length_m"] += length * factor
        row["area_m2"] += area * area_factor
        row["entities"] += 1

    thick = {str(k): float(v) for k, v in (thicknesses or {}).items() if v not in (None, "")}
    items = []
    for layer_name, row in sorted(layers.items(), key=lambda kv: kv[0]):
        t = thick.get(layer_name, 0.0)
        length_m = round(row["length_m"], 4)
        area_m2 = round(row["area_m2"], 4)
        if area_m2 >= 0.01 and area_m2 >= length_m * 0.05:
            qty, unit_qty, how = area_m2, "m2", "按封闭图形/填充面积"
            if t > 0:
                qty, unit_qty, how = round(area_m2 * t, 4), "m3", f"面积×厚度 {t}m"
        elif length_m >= 0.01:
            qty, unit_qty, how = length_m, "m", "按线长"
            if t > 0:
                qty, unit_qty, how = round(length_m * t, 4), "m2", f"长度×厚度 {t}m"
        elif row["count"]:
            qty, unit_qty, how = row["count"], "个", "按图块个数"
        else:
            continue
        items.append(
            {
                "layer": layer_name,
                "length_m": length_m,
                "area_m2": area_m2,
                "count": int(row["count"]),
                "entities": int(row["entities"]),
                "blocks": dict(row["blocks"]),
                "thickness_m": t or None,
                "qty": qty,
                "unit": unit_qty,
                "method": how,
            }
        )

    return {
        "filename": path.name,
        "insunits": insunits,
        "unit_label": unit_label,
        "unit_to_m": factor,
        "entity_count": total_ent,
        "skipped": skipped,
        "layer_count": len(items),
        "items": items,
        "note": "2D 图纸按图层统计。墙厚/板厚请在厚度栏填写后重算。标注层默认已跳过。",
    }


def export_qty_excel(result: dict[str, Any], dest: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "图纸工程量"
    ws.append(["图纸", result.get("filename"), "单位", result.get("unit_label"), "图元", result.get("entity_count")])
    ws.append([])
    ws.append(["图层", "长度(m)", "面积(m2)", "图块个数", "图元数", "厚度(m)", "工程量", "单位", "算法", "图块明细"])
    for it in result.get("items") or []:
        blocks = it.get("blocks") or {}
        detail = "、".join(f"{k}×{v}" for k, v in blocks.items()) if blocks else ""
        ws.append(
            [
                it.get("layer"),
                it.get("length_m"),
                it.get("area_m2"),
                it.get("count"),
                it.get("entities"),
                it.get("thickness_m") or "",
                it.get("qty"),
                it.get("unit"),
                it.get("method"),
                detail,
            ]
        )
    dest.parent.mkdir(parents=True, exist_ok=True)
    wb.save(dest)
    return dest
