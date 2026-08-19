import ezdxf
from fastapi.testclient import TestClient

from paiban.api import app
from paiban.engine.ceiling import layout_ceiling
from paiban.engine.generate import generate_layout
from paiban.engine.parse import load_catalog, parse_description
from paiban.engine.tiles import layout_floor, layout_wall

client = TestClient(app)


def test_parse_living_room_tiles():
    info = parse_description("客厅 4.8x6.2 层高2.8 铺800x800地砖")
    assert info["room"].kind == "客厅"
    assert abs(info["room"].width - 4.8) < 0.05
    assert abs(info["room"].depth - 6.2) < 0.05
    assert info["task"] == "floor"
    assert abs(info["floor_tile"]["w"] - 0.8) < 0.02
    assert info["project_type"] == "既有"
    assert abs(info["room"].openings[0].width - 0.80) < 0.02


def test_parse_new_build_door():
    info = parse_description("新建 客厅 4.8x6.2 层高3.0")
    assert info["project_type"] == "新建"
    assert abs(info["room"].openings[0].width - 0.90) < 0.02


def test_parse_bathroom_mm():
    info = parse_description("卫生间 2200×1800 墙砖 300x600")
    assert info["room"].kind == "卫生间"
    assert info["task"] == "wall"
    assert info["room"].width < 3
    assert abs(info["room"].openings[0].width - 0.70) < 0.02


def test_edge_tile_not_too_small():
    lay = layout_floor(4.85, 6.1, 0.8, 0.8, 0.002, "straight")
    assert lay["count"] >= 40
    assert lay["min_edge"] + 1e-6 >= 0.8 / 3


def test_generate_floor_svg_dxf():
    doc = generate_layout({"text": "客厅 4.8x6.2 地砖800x800", "task": "floor"})
    assert "<svg" in doc["svg"]
    assert doc["summary"]["count"] > 10
    assert (doc["zip"]).endswith(".zip")


def test_bathroom_floor_uses_antislip_and_slope_clause():
    doc = generate_layout({"text": "卫生间 2.2x1.8 层高2.4 地砖", "task": "floor"})
    assert "防滑" in doc["floor_tile"]["name"] or "防滑" in doc["floor_tile"].get("kind", "")
    codes = " ".join(c["code"] for c in doc["checks"])
    assert "55038" in codes and "4.1.10" in codes
    assert any("1％" in c["msg"] or "1%" in c["msg"] for c in doc["checks"])
    assert all(c["ok"] for c in doc["checks"] if c.get("hard", True) and "4.1.10" in c["code"])
    assert "地漏" in doc["svg"]
    assert "斜坡" in doc["svg"]
    assert any("4.1.12" in c["code"] and c["ok"] for c in doc["checks"])


def test_ceiling_gb50327_hangers():
    cat = load_catalog()
    spec = cat["ceilings"][0]
    ceil = layout_ceiling(4.8, 6.2, spec, wet=False, room_height=2.80, room_kind="客厅")
    assert ceil["mode"] == "full"
    assert ceil["hanger_end_ok"] is True
    assert ceil["hanger_span_ok"] is True
    assert ceil["hanger_max"] < 1.2
    assert ceil["secondary_spacing"] <= 0.60 + 1e-6
    assert 0.0048 - 1e-6 <= ceil["camber_m"] <= 0.0186 + 1e-6
    wet = layout_ceiling(2.2, 1.8, spec, wet=True, room_height=2.40, room_kind="卫生间")
    assert wet["secondary_spacing"] <= 0.40 + 1e-6


def test_ceiling_generate_clauses():
    doc = generate_layout({"text": "客厅 4.8x6.2 层高2.8 吊顶石膏板", "task": "ceiling"})
    assert doc["summary"]["main_m"] <= 1.001
    text = " ".join(c["msg"] + c["code"] for c in doc["checks"])
    assert "8.3.1" in text
    assert "300" in text
    assert doc["summary"]["mode"] == "full"
    assert doc["pass"] is True
    assert abs(doc["room"]["height"] - 2.8) < 1e-6


def test_low_storey_uses_local_ceiling():
    doc = generate_layout({"text": "客厅 4.8x6.2 层高2.7 吊顶石膏板", "task": "ceiling", "height": 2.7})
    assert doc["summary"]["mode"] == "local"
    assert "局部" in doc["svg"]
    assert any("1/3" in c["msg"] and c["ok"] for c in doc["checks"])
    assert doc["pass"] is True


def test_new_build_low_storey_fails():
    doc = generate_layout({"text": "新建 客厅 4.8x6.2 层高2.8 家具布置", "task": "furniture", "project_type": "新建", "height": 2.8})
    assert any("4.1.2-1" in c["code"] and c["ok"] is False for c in doc["checks"])
    assert doc["pass"] is False


def test_furniture_gb55038_bedroom():
    doc = generate_layout({"text": "主卧 3.6x4.5 层高2.8 家具布置", "task": "furniture", "room_kind": "卧室"})
    assert doc["summary"]["items"] >= 3
    assert "床" in doc["svg"]
    assert any("4.1.1" in c["code"] for c in doc["checks"])
    assert any("4.1.2" in c["code"] for c in doc["checks"])
    assert doc["pass"] is True


def test_kitchen_too_small_fails_area():
    doc = generate_layout({"text": "厨房 1.5x1.8 层高2.4 家具", "task": "furniture", "room_kind": "厨房", "width": 1.5, "depth": 1.8, "height": 2.4})
    assert any("4.1.4" in c["code"] and c["ok"] is False for c in doc["checks"])
    assert doc["pass"] is False


def test_entry_corridor_width():
    doc = generate_layout({"text": "玄关 1.00x2.40 层高2.8", "task": "furniture", "room_kind": "走廊", "room_name": "玄关", "width": 1.0, "depth": 2.4})
    assert any("4.1.13" in c["code"] and c["ok"] is False for c in doc["checks"])
    assert doc["pass"] is False


def test_gb50327_floor_cut_at_far_corner():
    lay = layout_floor(4.8, 6.2, 0.8, 0.8, 0.002, "straight")
    gy = lay["gy"]["widths"]
    assert abs(gy[0] - 0.8) < 0.006
    assert lay["min_edge"] + 1e-6 >= 0.8 / 3
    assert lay["n_cut_cols"] <= 2
    assert lay["n_cut_rows"] <= 2
    assert lay["first_row_whole_from_door"] is True
    assert lay["cut_mode_y"] in ("one_cut", "whole")


def test_gb50327_wall_one_cut_column_and_sleeve():
    holes = [{"x": 1.8, "y": 0.0, "w": 0.9, "h": 2.1}]
    lay = layout_wall(4.8, 2.8, 0.3, 0.6, 0.002, holes)
    assert lay["n_cut_cols"] <= 2
    assert lay["cut_mode_x"] in ("one_cut", "whole")
    assert lay["sleeved"] > 0
    assert lay["min_edge"] + 1e-6 >= 0.3 / 3
    doc = generate_layout({"text": "客厅 4.8x6.2 层高2.8 墙砖300x600", "task": "wall"})
    assert "阳角条" in doc["svg"]
    assert any("套割" in c["msg"] and c["ok"] for c in doc["checks"])
    assert any("12.3.1" in c["code"] and c.get("hard") is True and c["ok"] for c in doc["checks"])
    assert doc["pass"] is True


def test_gb50327_edge_is_code_not_craft():
    doc = generate_layout({"text": "客厅 4.8x6.2 地砖800x800", "task": "floor"})
    edge = [c for c in doc["checks"] if "1/3" in c["msg"] and "12.3.1" in c["code"]]
    assert edge
    assert all(c.get("hard") is True and c["ok"] for c in edge)
    assert "十字控制线" in doc["svg"]
    assert "门口整砖" in doc["svg"]
    assert doc["pass"] is True


def test_api_and_dxf_upload(tmp_path):
    r = client.get("/api/health").json()
    assert r["offline"] is True
    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (5000, 0), (5000, 4000), (0, 4000)], close=True)
    path = tmp_path / "r.dxf"
    doc.saveas(path)
    res = client.post("/api/upload", files={"file": ("r.dxf", path.read_bytes(), "application/dxf")}, data={"task": "floor"})
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["room"]["source"] == "CAD图纸"
    assert data["room"]["width"] >= 4.5
    z = client.get("/api/download/zip")
    assert z.status_code == 200
    assert z.content[:2] == b"PK"
