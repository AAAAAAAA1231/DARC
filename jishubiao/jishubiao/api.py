from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jishubiao import __app_name__, __version__
from jishubiao.config import DATA_DIR, STATIC_DIR, ensure_dirs
from jishubiao.engine.export import export_docx, export_markdown
from jishubiao.engine.generate import generate_bid, load_catalog

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class GenerateBody(BaseModel):
    name: str = "××住宅楼工程"
    location: str = ""
    owner: str = ""
    bidder: str = ""
    specialty: str = "房屋建筑"
    structure: str = "框剪"
    building_type: str = "住宅"
    residential: bool = True
    area: str = ""
    floors: str = ""
    duration: str = "540 日历天"
    seismic: str = "抗震设防烈度 7 度"
    foundation: str = "筏板基础"
    cost: str = ""
    quality_goal: str = "一次性验收合格"
    safety_goal: str = "杜绝较大及以上生产安全事故"
    notes: str = ""
    tender_text: str = ""
    include_codes: list[str] = Field(default_factory=list)
    exclude_codes: list[str] = Field(default_factory=list)


_LAST: dict[str, Any] = {}


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": 8792}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    data = load_catalog()
    return {
        "specialties": data["specialties"],
        "structures": data["structures"],
        "codes": [c for c in data["codes"] if c.get("name")],
        "avoid_old": data["avoid_old"],
    }


@app.post("/api/generate")
async def generate(body: GenerateBody) -> dict[str, Any]:
    ensure_dirs()
    doc = generate_bid(body.model_dump())
    _LAST.clear()
    _LAST.update(doc)
    md = export_markdown(doc)
    (DATA_DIR / "latest.md").write_text(md, encoding="utf-8")
    path = export_docx(doc)
    doc["docx"] = str(path)
    doc["markdown"] = md
    return doc


@app.get("/api/download/docx")
async def download_docx() -> FileResponse:
    doc = _LAST or generate_bid(GenerateBody().model_dump())
    if not _LAST:
        _LAST.update(doc)
    path = export_docx(doc)
    return FileResponse(path, filename=path.name, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")


@app.get("/api/download/md")
async def download_md() -> FileResponse:
    if not _LAST:
        generate_bid(GenerateBody().model_dump())
    ensure_dirs()
    path = DATA_DIR / "技术标.md"
    path.write_text(export_markdown(_LAST), encoding="utf-8")
    return FileResponse(path, filename=path.name, media_type="text/markdown; charset=utf-8")
