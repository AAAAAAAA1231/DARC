from __future__ import annotations

import json
import re
import zipfile
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

import ezdxf

from shigongtu.config import DATA_DIR, ensure_dirs
from shigongtu.engine.architecture import architecture_sheets
from shigongtu.engine.canvas import Drawing, new_sheet
from shigongtu.engine.layout import build_model
from shigongtu.engine.mep import (
    electrical_sheets,
    fire_sheets,
    heating_sheets,
    ventilation_sheets,
    water_sheets,
)
from shigongtu.engine.model import BuildingSpec
from shigongtu.engine.structure import structure_sheets

DISC_DIR = {
    "建筑": "01-建筑",
    "结构": "02-结构",
    "给排水": "03-给排水",
    "电气": "04-电气",
    "暖通": "05-暖通",
    "通风": "06-通风",
    "消防": "07-消防",
}


class _Num:
    def __init__(self) -> None:
        self.n: dict[str, int] = defaultdict(int)

    def __call__(self, prefix: str) -> str:
        self.n[prefix] += 1
        return f"{prefix}-{self.n[prefix]:02d}"


def _safe(name: str) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "_", name).strip() or "工程"
    return s[:40]


def _catalog(m, drawings: list[Drawing], number: str) -> Drawing:
    d = new_sheet(number, "图纸目录", "建筑", m)
    d.scale = 1
    d.paper_text(210, 26, "施 工 图 纸 目 录", 6.0)
    d.paper_text(210, 34, f"{m.spec.name}    {date.today().isoformat()}    共 {len(drawings)+1} 张", 2.6)
    headers = ["序号", "图号", "图名", "专业", "比例"]
    widths = [22, 40, 120, 40, 40]
    x0, y = 70, 44

    def row(vals, header=False, yi=y):
        x = x0
        for w, v in zip(widths, vals):
            d.paper_rect(x, yi, w, 6.2, lw=0.18, fill="#e8eef6" if header else "none")
            d.paper_text(x + w / 2, yi + 3.1, str(v)[:22], 2.2)
            x += w

    row(headers, True, y)
    y += 6.2
    items = [(number, "图纸目录", "建筑", "—")] + [
        (x.number, x.name, x.discipline, f"1:{x.scale}" if x.scale > 1 else "—") for x in drawings
    ]
    for i, (no, name, disc, sc) in enumerate(items, 1):
        if y > 235:
            break
        row([i, no, name, disc, sc], False, y)
        y += 6.2
    d.paper_text(40, 250, "本目录含建筑、结构、给排水、电气、采暖、通风、消防。深度为方案/初步设计示意。", 2.4, "s")
    return d


def generate_package(params: dict[str, Any], out_dir: Path | None = None) -> dict[str, Any]:
    ensure_dirs()
    spec = BuildingSpec.from_dict(params)
    model = build_model(spec)
    num = _Num()
    drawings: list[Drawing] = []
    drawings += architecture_sheets(model, num)
    drawings += structure_sheets(model, num)
    drawings += water_sheets(model, num)
    drawings += electrical_sheets(model, num)
    drawings += heating_sheets(model, num)
    drawings += ventilation_sheets(model, num)
    drawings += fire_sheets(model, num)
    catalog = _catalog(model, drawings, "建施-00")
    catalog.number = "建施-00"
    catalog.name = "图纸目录"
    drawings = [catalog] + drawings

    root = out_dir or (DATA_DIR / _safe(spec.name))
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file():
                p.unlink()
    root.mkdir(parents=True, exist_ok=True)
    (root / "cad").mkdir(exist_ok=True)
    meta = []
    for i, dr in enumerate(drawings):
        folder = root / DISC_DIR.get(dr.discipline, "00-其他")
        folder.mkdir(exist_ok=True)
        svg_name = f"{dr.number}_{dr.name}.svg".replace("/", "-")
        svg_path = folder / svg_name
        svg_path.write_text(dr.to_svg(), encoding="utf-8")
        dxf_path = root / "cad" / f"{dr.number}_{dr.name}.dxf".replace("/", "-")
        doc = ezdxf.new("R2010", setup=True)
        doc.header["$INSUNITS"] = 4  # mm
        dr.to_dxf(doc)
        doc.saveas(dxf_path)
        meta.append(
            {
                "id": i,
                "number": dr.number,
                "name": dr.name,
                "discipline": dr.discipline,
                "scale": dr.scale,
                "svg": str(svg_path.relative_to(root)).replace("\\", "/"),
                "dxf": str(dxf_path.relative_to(root)).replace("\\", "/"),
            }
        )
    index = {
        "summary": model.summary(),
        "warnings": model.warnings,
        "drawings": meta,
        "date": date.today().isoformat(),
    }
    (root / "index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "index.html").write_text(_gallery_html(index, spec.name), encoding="utf-8")
    zip_path = DATA_DIR / f"{_safe(spec.name)}_施工图.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in root.rglob("*"):
            if p.is_file():
                zf.write(p, p.relative_to(root.parent))
    index["out_dir"] = str(root)
    index["zip"] = str(zip_path)
    index["count"] = len(drawings)
    return index


def _gallery_html(index: dict[str, Any], name: str) -> str:
    sm = index["summary"]
    warns = "".join(f"<li>{w}</li>" for w in index["warnings"])
    cards = []
    for d in index["drawings"]:
        cards.append(
            f'<a class="card" href="{d["svg"]}"><div class="no">{d["number"]}</div>'
            f'<div class="nm">{d["name"]}</div><div class="ds">{d["discipline"]} 1:{d["scale"]}</div></a>'
        )
    return f"""<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="utf-8"/><title>{name} 施工图</title>
<style>
body{{font-family:"Microsoft YaHei",sans-serif;background:#f3f6fb;margin:0;color:#1c2a3a}}
h1{{background:#12365f;color:#fff;margin:0;padding:16px 24px;font-size:20px}}
.meta{{padding:12px 24px;background:#eef4fb}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;padding:16px 24px}}
.card{{background:#fff;border:1px solid #d7e0ea;border-radius:10px;padding:12px;text-decoration:none;color:inherit}}
.no{{color:#1b4f8a;font-weight:700}}
.ds{{color:#5e7186;font-size:12px;margin-top:4px}}
</style></head><body>
<h1>{name} · 全套施工图（示意）</h1>
<div class="meta">
<p>{sm['building_type']}　地上{sm['floors']}层　单层{sm['floor_area']}㎡　总面积{sm['total_area']}㎡　
{sm['length']}×{sm['width']}m　{sm['structure']}　抗震{sm['seismic']}</p>
<ul>{warns}</ul>
</div>
<div class="grid">{''.join(cards)}</div>
</body></html>"""
