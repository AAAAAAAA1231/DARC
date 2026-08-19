import ezdxf
from fastapi.testclient import TestClient

from paiban.api import app
from paiban.engine.generate import generate_layout
from paiban.engine.parse import parse_description
from paiban.engine.tiles import layout_floor


client = TestClient(app)


def test_parse_living_room_tiles():
    info = parse_description("客厅 4.8x6.2 层高2.8 铺800x800地砖")
    assert info["room"].kind == "客厅"
    assert abs(info["room"].width - 4.8) < 0.05
    assert abs(info["room"].depth - 6.2) < 0.05
    assert info["task"] == "floor"
    assert abs(info["floor_tile"]["w"] - 0.8) < 0.02


def test_parse_bathroom_mm():
    info = parse_description("卫生间 2200×1800 墙砖 300x600")
    assert info["room"].kind == "卫生间"
    assert info["task"] == "wall"
    assert info["room"].width < 3


def test_edge_tile_not_too_small():
    lay = layout_floor(4.85, 6.1, 0.8, 0.8, 0.002, "straight")
    assert lay["count"] >= 40
    assert lay["min_edge"] + 1e-6 >= 0.8 / 3


def test_generate_floor_svg_dxf():
    doc = generate_layout({"text": "客厅 4.8x6.2 地砖800x800", "task": "floor"})
    assert "<svg" in doc["svg"]
    assert doc["summary"]["count"] > 10
    assert (doc["zip"]).endswith(".zip")


def test_ceiling_main_spacing():
    doc = generate_layout({"text": "客厅 4.8x6.2 吊顶石膏板", "task": "ceiling"})
    assert doc["summary"]["main_m"] <= 1.001
    assert any("主龙骨" in c["msg"] for c in doc["checks"])


def test_furniture_bedroom():
    doc = generate_layout({"text": "主卧 3.6x4.5 家具布置", "task": "furniture", "room_kind": "卧室"})
    assert doc["summary"]["items"] >= 3
    assert "床" in doc["svg"]


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
