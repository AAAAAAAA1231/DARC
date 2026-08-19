from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from xiaoguotu import __app_name__, __version__
from xiaoguotu.config import STATIC_DIR, ensure_dirs
from xiaoguotu.engine.preset import build_scene, catalogs

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_LAST: dict[str, Any] = {}


class SceneBody(BaseModel):
    mode: str = "exterior"
    name: str = "××办公楼效果图"
    building_type: str = "办公楼"
    floors: int = Field(default=18, ge=1, le=80)
    floor_h: float = 3.6
    length: float = 48
    width: float = 24
    facade: str = "玻璃幕墙"
    interior_room: str = "办公室"
    interior_style: str = "现代"
    time: str = "上午"
    lens_mm: int = 24
    camera_h: float = 1.7
    two_point: bool = True
    output: str = "1080p"
    quality: str = "成图 High"
    renderer: str = "V-Ray 6"
    entourage: bool = True
    bloom: bool = False


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": 8798}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    return catalogs()


@app.post("/api/scene")
async def scene(body: SceneBody) -> dict[str, Any]:
    ensure_dirs()
    doc = build_scene(body.model_dump())
    _LAST.clear()
    _LAST.update(doc)
    return {"ok": True, "scene": doc}


@app.get("/api/download/max-sheet")
async def download_sheet() -> PlainTextResponse:
    text = _LAST.get("max_sheet") or build_scene(SceneBody().model_dump())["max_sheet"]
    return PlainTextResponse(
        text,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="3dsMax-VRay-preset.txt"'},
    )
