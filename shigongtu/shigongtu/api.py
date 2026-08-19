from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from shigongtu import __app_name__, __version__
from shigongtu.config import DATA_DIR, STATIC_DIR, ensure_dirs
from shigongtu.engine.generate import generate_package
from shigongtu.engine.model import CLIMATES, FIRE_RATINGS, FOUNDATIONS, PRESETS, STRUCTURES

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_LAST: dict[str, Any] = {}


class GenerateBody(BaseModel):
    name: str = "××办公楼工程"
    location: str = "某市"
    client: str = ""
    designer: str = "施工图生成器"
    building_type: str = "办公楼"
    floors: int = Field(default=6, ge=1, le=40)
    basement: int = Field(default=0, ge=0, le=3)
    floor_area: float = 1200
    total_area: float = 0
    floor_height: float = 0
    length: float = 0
    width: float = 0
    span_x: float = 0
    span_y: float = 0
    structure: str = ""
    seismic: str = "7度"
    fire_rating: str = "二级"
    climate: str = "夏热冬冷"
    foundation: str = ""
    notes: str = ""


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": 8796}


@app.get("/api/presets")
async def presets() -> dict[str, Any]:
    return {
        "building_types": list(PRESETS.keys()),
        "structures": STRUCTURES,
        "climates": CLIMATES,
        "fire_ratings": FIRE_RATINGS,
        "foundations": FOUNDATIONS,
        "presets": PRESETS,
        "seismic": ["6度", "7度", "8度", "9度"],
    }


@app.post("/api/generate")
async def generate(body: GenerateBody) -> dict[str, Any]:
    ensure_dirs()
    doc = generate_package(body.model_dump())
    _LAST.clear()
    _LAST.update(doc)
    return {
        "ok": True,
        "summary": doc["summary"],
        "warnings": doc["warnings"],
        "drawings": doc["drawings"],
        "count": doc["count"],
        "zip": "/api/download/zip",
    }


@app.get("/api/drawing/{item_id}/svg")
async def drawing_svg(item_id: int) -> FileResponse:
    if not _LAST:
        raise HTTPException(404, "尚未生成图纸")
    drawings = _LAST.get("drawings") or []
    if item_id < 0 or item_id >= len(drawings):
        raise HTTPException(404, "图纸不存在")
    path = Path(_LAST["out_dir"]) / drawings[item_id]["svg"]
    if not path.exists():
        raise HTTPException(404, "文件缺失")
    return FileResponse(path, media_type="image/svg+xml")


@app.get("/api/drawing/{item_id}/dxf")
async def drawing_dxf(item_id: int) -> FileResponse:
    if not _LAST:
        raise HTTPException(404, "尚未生成图纸")
    drawings = _LAST.get("drawings") or []
    if item_id < 0 or item_id >= len(drawings):
        raise HTTPException(404, "图纸不存在")
    path = Path(_LAST["out_dir"]) / drawings[item_id]["dxf"]
    return FileResponse(path, filename=path.name, media_type="application/dxf")


@app.get("/api/download/zip")
async def download_zip() -> FileResponse:
    if not _LAST.get("zip"):
        raise HTTPException(404, "尚未生成图纸")
    path = Path(_LAST["zip"])
    return FileResponse(path, filename=path.name, media_type="application/zip")


@app.get("/api/download/index")
async def download_index() -> FileResponse:
    if not _LAST.get("out_dir"):
        raise HTTPException(404, "尚未生成图纸")
    path = Path(_LAST["out_dir"]) / "index.html"
    return FileResponse(path, filename="图纸目录.html", media_type="text/html; charset=utf-8")
