from __future__ import annotations

from typing import Any

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from paiban import __app_name__, __version__
from paiban.config import DATA_DIR, STATIC_DIR, ensure_dirs
from paiban.engine.parse import load_catalog
from paiban.engine.generate import generate_layout

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_LAST: dict[str, Any] = {}


class LayoutBody(BaseModel):
    text: str = "客厅 4.8x6.2 层高2.8 铺800x800地砖"
    task: str = ""
    room_kind: str = ""
    room_name: str = ""
    width: float = 0
    depth: float = 0
    height: float = 0
    floor_tile: str = ""
    wall_tile: str = ""
    ceiling: str = ""
    project_type: str = "既有"
    pattern: str = ""


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": 8799}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    return load_catalog()


def _safe(params: dict[str, Any], blob: bytes | None = None, filename: str = "") -> dict[str, Any] | JSONResponse:
    try:
        return _run(params, blob, filename)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc) or exc.__class__.__name__}, status_code=500)


def _run(params: dict[str, Any], blob: bytes | None = None, filename: str = "") -> dict[str, Any]:
    ensure_dirs()
    doc = generate_layout(params, blob, filename)
    _LAST.clear()
    _LAST.update(doc)
    return {
        "ok": True,
        "room": doc["room"],
        "task": doc["task"],
        "svg": doc["svg"],
        "checks": doc["checks"],
        "qty": doc["qty"],
        "codes": doc["codes"],
        "warnings": doc["warnings"],
        "pass": doc["pass"],
        "summary": doc["summary"],
        "floor_tile": doc["floor_tile"],
        "wall_tile": doc["wall_tile"],
        "ceiling": doc["ceiling"],
        "project_type": doc.get("project_type"),
        "pattern": doc["pattern"],
    }


@app.post("/api/layout", response_model=None)
async def layout(body: LayoutBody):
    return _safe(body.model_dump())


@app.post("/api/upload", response_model=None)
async def upload(
    file: UploadFile = File(...),
    task: str = Form(""),
    text: str = Form(""),
    project_type: str = Form("既有"),
    room_kind: str = Form(""),
    width: str = Form(""),
    depth: str = Form(""),
    height: str = Form(""),
    floor_tile: str = Form(""),
    wall_tile: str = Form(""),
    ceiling: str = Form(""),
    pattern: str = Form(""),
):
    blob = await file.read()
    params = {
        "text": text,
        "task": task,
        "project_type": project_type,
        "room_kind": room_kind,
        "floor_tile": floor_tile,
        "wall_tile": wall_tile,
        "ceiling": ceiling,
        "pattern": pattern,
    }
    if width:
        params["width"] = float(width)
    if depth:
        params["depth"] = float(depth)
    if height:
        params["height"] = float(height)
    return _safe(params, blob, file.filename or "")


@app.get("/api/download/svg")
async def dl_svg() -> Response:
    svg = _LAST.get("svg") or ""
    return Response(svg, media_type="image/svg+xml", headers={"Content-Disposition": "attachment; filename=layout.svg"})


@app.get("/api/download/dxf")
async def dl_dxf() -> FileResponse:
    path = DATA_DIR / "latest" / "layout.dxf"
    if not path.exists():
        generate_layout({})
    return FileResponse(path, filename="layout.dxf", media_type="application/dxf")


@app.get("/api/download/zip")
async def dl_zip() -> FileResponse:
    path = DATA_DIR / "装修排版.zip"
    if not path.exists():
        generate_layout({})
    return FileResponse(path, filename="装修排版.zip", media_type="application/zip")
