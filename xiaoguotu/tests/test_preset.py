from xiaoguotu.engine.preset import build_scene, catalogs, default_params


def test_catalog_has_requested_modes():
    names = {m["name"] for m in catalogs()["modes"]}
    assert "室内效果图" in names
    assert "大楼外观" in names
    assert "整体平面" in names
    assert "鸟瞰效果图" in names
    assert "夜景外观" in names


def test_interior_physical_camera():
    s = build_scene({"mode": "interior", "building_type": "住宅"})
    assert s["camera"]["lens_mm"] == 35
    assert s["camera"]["height_m"] == 1.6
    assert "VRay" in s["camera"]["type"] or "Physical" in s["camera"]["type"]
    assert s["building"]["type"] == "住宅"


def test_exterior_sun_and_output():
    s = build_scene({"mode": "exterior", "time": "黄昏", "output": "4k", "quality": "成图 High"})
    assert s["sun"]["altitude"] == 8
    assert s["output"]["width"] == 3840
    assert s["sampler"]["max"] == 24
    assert "VRaySun" in s["max_sheet"]
    assert "两点透视" in s["max_sheet"]


def test_night_forces_night_time():
    s = build_scene({"mode": "night", "time": "正午"})
    assert s["sun"]["time"] == "夜晚"
    assert s["mode"]["id"] == "night"


def test_default_params_mode():
    d = default_params("siteplan")
    assert d["mode"] == "siteplan"
    assert d["lens_mm"] == 50
