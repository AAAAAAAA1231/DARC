from __future__ import annotations

from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient

from shexiangtou.api import app
from shexiangtou.engine.parse import parse_description
from shexiangtou.engine.place import layout_cameras

ROOT = Path(__file__).resolve().parents[1]


def test_parse_office_text():
    scene = parse_description("办公室 12x8 层高3.0 2个门")
    assert scene.width_m == 12.0
    assert scene.depth_m == 8.0
    assert scene.height_m == 3.0
    assert scene.space_type == "办公室"
    assert len(scene.doors) == 2


def test_office_layout_covers_and_picks_camera():
    result = layout_cameras({"description": "办公室 12x8 层高3.0 2个门"})
    assert result["ok"] is True
    assert result["n"] >= 2
    assert result["cover"] >= 95
    assert result["pass"] is True
    assert "<svg" in result["svg"]
    assert any(c["role"].startswith("入口") for c in result["cameras"])
    kinds = {c["camera"]["kind"] for c in result["cameras"]}
    assert kinds & {"半球", "筒型", "人脸", "鱼眼"}


def test_corridor_layout():
    result = layout_cameras(
        {
            "space_type": "走廊",
            "width_m": 18,
            "depth_m": 2.1,
            "height_m": 2.8,
            "doors": 2,
        }
    )
    assert result["ok"] is True
    assert result["n"] >= 2
    assert result["cover"] >= 90
    assert result["pass"] is True


def test_parking_uses_outdoor_camera():
    result = layout_cameras({"description": "停车场 30x20 层高无 室外"})
    assert result["ok"] is True
    assert result["n"] >= 1
    assert all(c["camera"]["kind"] in ("枪机", "球机") for c in result["cameras"])


def test_api_layout_and_zip():
    client = TestClient(app)
    r = client.post("/api/layout", json={"description": "会议室 8x6 1个门"})
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["n"] >= 1
    z = client.get("/api/download/zip")
    assert z.status_code == 200
    assert z.content[:2] == b"PK"


def test_cad_upload_closed_polyline():
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (10000, 0), (10000, 8000), (0, 8000)],
        close=True,
        dxfattribs={"layer": "0"},
    )
    msp.add_line((4000, 0), (5000, 0), dxfattribs={"layer": "DOOR"})
    buf = StringIO()
    doc.write(buf)
    payload = buf.getvalue().encode("utf-8")
    client = TestClient(app)
    r = client.post(
        "/api/upload",
        files={"file": ("room.dxf", payload, "application/dxf")},
        data={"space_type": "办公室", "purpose": "观察"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["room"]["source"] == "CAD图纸"
    assert abs(data["room"]["width_m"] - 10.0) < 0.05
    assert abs(data["room"]["depth_m"] - 8.0) < 0.05
    assert data["n"] >= 2
    assert data["cover"] >= 90


def test_static_index():
    html = (ROOT / "shexiangtou" / "static" / "index.html").read_text(encoding="utf-8")
    assert "摄像头布置" in html
    js = (ROOT / "shexiangtou" / "static" / "js" / "app.js").read_text(encoding="utf-8")
    assert "/api/layout" in js
