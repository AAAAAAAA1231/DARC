from shigongtu.engine.generate import generate_package
from shigongtu.engine.layout import build_model
from shigongtu.engine.model import BuildingSpec, PRESETS


def test_presets_cover_requested_types():
    for t in ("办公楼", "住宅", "商业", "厂房", "学校", "医院", "酒店"):
        assert t in PRESETS


def test_office_grid_and_stairs(tmp_path):
    spec = BuildingSpec.from_dict(
        {
            "name": "测试办公楼",
            "building_type": "办公楼",
            "floors": 6,
            "basement": 1,
            "floor_area": 1200,
            "span_x": 8.4,
            "span_y": 8.4,
        }
    )
    m = build_model(spec)
    assert m.nx >= 2 and m.ny >= 2
    assert m.n_stairs >= 2
    assert 1 in m.plans and -1 in m.plans
    kinds = {r.kind for r in m.plans[1].rooms}
    assert "楼梯" in kinds
    assert "办公" in kinds
    assert m.columns


def test_residential_units():
    m = build_model(BuildingSpec.from_dict({"building_type": "住宅", "floors": 6, "floor_area": 640}))
    names = " ".join(r.name + r.kind for r in m.plans[2].rooms)
    assert "客厅" in names and "卧室" in names and "厨房" in names


def test_generate_full_set(tmp_path):
    doc = generate_package(
        {
            "name": "单元测试楼",
            "building_type": "办公楼",
            "floors": 4,
            "basement": 0,
            "floor_area": 800,
        },
        out_dir=tmp_path / "out",
    )
    discs = {d["discipline"] for d in doc["drawings"]}
    for x in ("建筑", "结构", "给排水", "电气", "暖通", "通风", "消防"):
        assert x in discs, x
    assert doc["count"] >= 24
    numbers = [d["number"] for d in doc["drawings"]]
    assert "建施-00" in numbers
    assert any(n.startswith("结施") for n in numbers)
    assert any(n.startswith("水施") for n in numbers)
    assert any(n.startswith("电施") for n in numbers)
    assert any(n.startswith("暖施") for n in numbers)
    assert any(n.startswith("风施") for n in numbers)
    assert any(n.startswith("消施") for n in numbers)
    svg = tmp_path / "out" / doc["drawings"][1]["svg"]
    assert svg.exists() and "svg" in svg.read_text(encoding="utf-8")[:200]
    dxf = tmp_path / "out" / doc["drawings"][1]["dxf"]
    assert dxf.exists() and dxf.stat().st_size > 400
    assert (tmp_path / "out" / "index.html").exists()
    assert doc["warnings"]


def test_factory_steel():
    m = build_model(BuildingSpec.from_dict({"building_type": "厂房", "floors": 1, "floor_area": 2400, "structure": "钢结构"}))
    kinds = {r.kind for r in m.plans[1].rooms}
    assert "车间" in kinds
    assert m.spec.structure == "钢结构"
