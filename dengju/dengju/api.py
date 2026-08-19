from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from dengju import __app_name__, __version__
from dengju.config import DATA_DIR, STATIC_DIR, ensure_dirs
from dengju.engine.parse import load_catalog
from dengju.engine.select import select_lighting

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_LAST: dict[str, Any] = {}


class Body(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    description: str = Field(default="")
    text: str = Field(default="")
    room_type: str = Field(default="")
    fixture_id: str = Field(default="")
    width_m: float = Field(default=0)
    depth_m: float = Field(default=0)
    height_m: float = Field(default=0)
    width: float = Field(default=0)
    depth: float = Field(default=0)
    height: float = Field(default=0)
    illuminance_lx: float = Field(default=0)
    E: float = Field(default=0)
    mf: float = Field(default=0)
    work_plane_m: float = Field(default=0)
    work_h: float = Field(default=0)
    cct: int = Field(default=4000)
    ra_min: int = Field(default=0)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": 8801}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    raw = load_catalog()
    rooms = []
    for room in raw["rooms"]:
        rooms.append(
            {
                **room,
                "id": room.get("id") or room["name"],
                "UGR": room.get("UGR", room.get("ugr")),
                "Ra": room.get("Ra", room.get("ra")),
            }
        )
    fixtures = []
    for fx in raw["fixtures"]:
        fixtures.append(
            {
                **fx,
                "P": fx.get("P", fx.get("W")),
                "Phi": fx.get("Phi", fx.get("lm")),
            }
        )
    return {"rooms": rooms, "fixtures": fixtures}


def _run(params: dict[str, Any], blob: bytes | None = None, filename: str = "") -> dict[str, Any]:
    ensure_dirs()
    doc = select_lighting(params, blob, filename)
    _LAST.clear()
    _LAST.update(doc)
    return {k: v for k, v in doc.items() if k != "zip"}


@app.post("/api/select")
async def select(body: Body) -> dict[str, Any]:
    return _run(body.model_dump())


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    description: str = Form(""),
    text: str = Form(""),
    room_type: str = Form(""),
    fixture_id: str = Form(""),
    width_m: float = Form(0),
    depth_m: float = Form(0),
    height_m: float = Form(0),
    illuminance_lx: float = Form(0),
    mf: float = Form(0),
    work_plane_m: float = Form(0),
    cct: int = Form(4000),
    ra_min: int = Form(0),
) -> dict[str, Any]:
    blob = await file.read()
    return _run(
        {
            "description": description,
            "text": text,
            "room_type": room_type,
            "fixture_id": fixture_id,
            "width_m": width_m,
            "depth_m": depth_m,
            "height_m": height_m,
            "illuminance_lx": illuminance_lx,
            "mf": mf,
            "work_plane_m": work_plane_m,
            "cct": cct,
            "ra_min": ra_min,
        },
        blob,
        file.filename or "",
    )


@app.get("/api/download/svg")
async def dl_svg() -> Response:
    return Response(
        _LAST.get("svg") or "",
        media_type="image/svg+xml",
        headers={"Content-Disposition": "attachment; filename=layout.svg"},
    )


@app.get("/api/download/dxf")
async def dl_dxf() -> FileResponse:
    path = DATA_DIR / "latest" / "layout.dxf"
    if not path.exists():
        select_lighting({})
    return FileResponse(path, filename="lighting.dxf", media_type="application/dxf")


@app.get("/api/download/zip")
async def dl_zip() -> FileResponse:
    path = DATA_DIR / "灯具选型.zip"
    if not path.exists():
        select_lighting({})
    return FileResponse(path, filename="灯具选型.zip", media_type="application/zip")
