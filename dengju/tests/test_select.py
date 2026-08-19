from __future__ import annotations

from io import StringIO
from pathlib import Path

from fastapi.testclient import TestClient

from dengju.api import app
from dengju.engine.parse import parse_description
from dengju.engine.select import select_lighting

ROOT = Path(__file__).resolve().parents[1]


def test_parse_office_text():
    room = parse_description("普通办公室 7.2x9.0 层高2.8 300lx")
    assert room.width_m == 7.2
    assert room.depth_m == 9.0
    assert room.height_m == 2.8
    assert room.illuminance_lx == 300
    assert room.room_type == "普通办公室"


def test_select_office_qty():
    result = select_lighting(
        {
            "description": "普通办公室 7.2x9.0 层高2.8 300lx",
            "width_m": 0,
            "depth_m": 0,
            "height_m": 0,
        }
    )
    assert result["ok"] is True
    assert result["n"] >= 4
    assert result["e_avg"] >= 280
    assert "<svg" in result["svg"]
    assert result["fixture"]["id"] == "panel36"


def test_classroom_via_room_type():
    result = select_lighting(
        {
            "room_type": "普通教室",
            "width_m": 9.0,
            "depth_m": 7.2,
            "height_m": 3.3,
        }
    )
    assert result["ok"] is True
    assert result["n"] >= 6
    assert result["checks"][0]["ok"] is True


def test_api_select_and_zip():
    client = TestClient(app)
    r = client.post(
        "/api/select",
        json={"description": "会议室 6x8 层高3.0 300lx"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    z = client.get("/api/download/zip")
    assert z.status_code == 200
    assert z.content[:2] == b"PK"


def test_cad_upload_closed_polyline():
    import ezdxf

    doc = ezdxf.new()
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (8000, 0), (8000, 6000), (0, 6000)],
        close=True,
        dxfattribs={"layer": "0"},
    )
    buf = StringIO()
    doc.write(buf)
    payload = buf.getvalue().encode("utf-8")

    client = TestClient(app)
    r = client.post(
        "/api/upload",
        files={"file": ("room.dxf", payload, "application/dxf")},
        data={"room_type": "普通办公室", "illuminance_lx": "300"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert data["room"]["source"] == "CAD图纸"
    assert abs(data["room"]["width_m"] - 8.0) < 0.05
    assert abs(data["room"]["depth_m"] - 6.0) < 0.05
    assert data["n"] >= 4
    z = client.get("/api/download/zip")
    assert z.content[:2] == b"PK"


def test_static_index():
    html = (ROOT / "dengju" / "static" / "index.html").read_text(encoding="utf-8")
    assert "灯具选型" in html
    assert "/api/select" in (ROOT / "dengju" / "static" / "js" / "app.js").read_text(
        encoding="utf-8"
    )
