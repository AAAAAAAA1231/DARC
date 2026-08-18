from __future__ import annotations

from pathlib import Path

import ezdxf

from qingbiao.engine.cad_qty import analyze_dxf, export_qty_excel


def test_dxf_length_area_and_blocks(tmp_path: Path):
    doc = ezdxf.new("R2010")
    doc.header["$INSUNITS"] = 4  # mm
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (10000, 0), (10000, 5000), (0, 5000)], close=True, dxfattribs={"layer": "房间"})
    msp.add_line((0, 0), (8000, 0), dxfattribs={"layer": "墙"})
    blk = doc.blocks.new("DOOR")
    blk.add_line((0, 0), (900, 0))
    msp.add_blockref("DOOR", (1000, 1000), dxfattribs={"layer": "门"})
    msp.add_blockref("DOOR", (3000, 1000), dxfattribs={"layer": "门"})
    msp.add_text("标注文字", dxfattribs={"layer": "标注"}).set_placement((0, 0))
    path = tmp_path / "demo.dxf"
    doc.saveas(path)

    out = analyze_dxf(path, unit="mm", skip_annot=True)
    by = {i["layer"]: i for i in out["items"]}
    assert "房间" in by
    assert abs(by["房间"]["area_m2"] - 50.0) < 0.2
    assert abs(by["墙"]["length_m"] - 8.0) < 0.05
    assert by["门"]["count"] == 2
    assert "标注" not in by

    thick = analyze_dxf(path, unit="mm", skip_annot=True, thicknesses={"墙": 0.2})
    wall = {i["layer"]: i for i in thick["items"]}["墙"]
    assert wall["unit"] == "m2"
    assert abs(wall["qty"] - 1.6) < 0.05

    xlsx = export_qty_excel(out, tmp_path / "qty.xlsx")
    assert xlsx.exists()


def test_dwg_rejected(tmp_path: Path):
    fake = tmp_path / "a.dwg"
    fake.write_bytes(b"AC1024")
    try:
        analyze_dxf(fake)
        assert False, "should reject dwg"
    except ValueError as exc:
        assert "DXF" in str(exc)
