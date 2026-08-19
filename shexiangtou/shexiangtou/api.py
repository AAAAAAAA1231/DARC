from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from shexiangtou import __app_name__, __version__
from shexiangtou.config import DATA_DIR, STATIC_DIR, ensure_dirs
from shexiangtou.engine.parse import load_catalog
from shexiangtou.engine.place import layout_cameras

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_LAST: dict[str, Any] = {}


class Body(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    description: str = Field(default="")
    text: str = Field(default="")
    space_type: str = Field(default="")
    room_type: str = Field(default="")
    purpose: str = Field(default="")
    width_m: float = Field(default=0)
    depth_m: float = Field(default=0)
    height_m: float = Field(default=0)
    doors: int = Field(default=0)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": 8802}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    raw = load_catalog()
    spaces = [{**s, "id": s["id"]} for s in raw["spaces"]]
    cameras = [
        {
            **c,
            "P": c.get("W"),
        }
        for c in raw["cameras"]
    ]
    return {"spaces": spaces, "cameras": cameras, "purposes": ["监视", "观察", "识别", "辨认"]}


def _run(params: dict[str, Any], blob: bytes | None = None, filename: str = "") -> dict[str, Any]:
    ensure_dirs()
    doc = layout_cameras(params, blob, filename)
    _LAST.clear()
    _LAST.update(doc)
    return {k: v for k, v in doc.items() if k != "zip"}


@app.post("/api/layout")
async def layout(body: Body) -> dict[str, Any]:
    return _run(body.model_dump())


@app.post("/api/upload")
async def upload(
    file: UploadFile = File(...),
    description: str = Form(""),
    text: str = Form(""),
    space_type: str = Form(""),
    purpose: str = Form(""),
    width_m: float = Form(0),
    depth_m: float = Form(0),
    height_m: float = Form(0),
    doors: int = Form(0),
) -> dict[str, Any]:
    blob = await file.read()
    return _run(
        {
            "description": description,
            "text": text,
            "space_type": space_type,
            "purpose": purpose,
            "width_m": width_m,
            "depth_m": depth_m,
            "height_m": height_m,
            "doors": doors,
        },
        blob,
        file.filename or "",
    )


@app.get("/api/download/svg")
async def dl_svg() -> Response:
    return Response(
        _LAST.get("svg") or "",
        media_type="image/svg+xml",
        headers={"Content-Disposition": "attachment; filename=cameras.svg"},
    )


@app.get("/api/download/dxf")
async def dl_dxf() -> FileResponse:
    path = DATA_DIR / "latest" / "layout.dxf"
    if not path.exists():
        layout_cameras({})
    return FileResponse(path, filename="cameras.dxf", media_type="application/dxf")


@app.get("/api/download/zip")
async def dl_zip() -> FileResponse:
    path = DATA_DIR / "摄像头布置.zip"
    if not path.exists():
        layout_cameras({})
    return FileResponse(path, filename="摄像头布置.zip", media_type="application/zip")
