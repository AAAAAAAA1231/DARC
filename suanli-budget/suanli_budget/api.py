from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from suanli_budget import __app_name__, __version__
from suanli_budget.config import STATIC_DIR, ensure_dirs
from suanli_budget.engine.calc import compile_budget, load_catalog
from suanli_budget.engine.export import export_docx, export_excel

ensure_dirs()
app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

_last: dict[str, Any] = {}


class BudgetBody(BaseModel):
    project: str = "算力中心一期"
    location: str = ""
    mode: str = "pflops"  # pflops | count
    target_pflops: float = 10.0
    gpu_count: int = 64
    gpu_id: str = "h20-141"
    cooling: str = "liquid"
    include_cpu_ram: bool = False
    gpu: dict[str, Any] = Field(default_factory=dict)
    prices: dict[str, Any] = Field(default_factory=dict)


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    return load_catalog()


@app.post("/api/budget")
async def make_budget(body: BudgetBody) -> dict[str, Any]:
    try:
        out = compile_budget(body.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _last["budget"] = out
    return out


@app.get("/api/budget/excel")
async def excel() -> FileResponse:
    if not _last.get("budget"):
        raise HTTPException(400, "请先生成预算")
    path = export_excel(_last["budget"])
    return FileResponse(
        path,
        filename="算力中心预算表.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@app.get("/api/budget/docx")
async def docx() -> FileResponse:
    if not _last.get("budget"):
        raise HTTPException(400, "请先生成预算")
    path = export_docx(_last["budget"])
    return FileResponse(
        path,
        filename="算力中心预算书.docx",
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
