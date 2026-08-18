from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from qingbiao import __app_name__, __version__
from qingbiao.config import MIN_BIDDERS, STATIC_DIR
from qingbiao.engine.economic import compare_to_limit, cross_compare_prices, parse_excel_bid
from qingbiao.engine.metadata import compare_file_properties, extract_file_properties
from qingbiao.engine.report import build_report
from qingbiao.engine.technical import cross_similar, extract_text, split_paragraphs, validate_one
from qingbiao.store import store

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ProjectBody(BaseModel):
    name: str = ""
    floors: str = ""
    area: str | float | None = ""
    structure: str = ""
    foundation: str = ""
    seismic: str = ""
    notes: str = ""
    settings: dict[str, Any] | None = None


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True}


@app.get("/api/session")
async def get_session() -> dict[str, Any]:
    return store.data


@app.post("/api/reset")
async def reset() -> dict[str, Any]:
    store.reset()
    return store.data


@app.post("/api/project")
async def save_project(body: ProjectBody) -> dict[str, Any]:
    payload = body.model_dump()
    settings = payload.pop("settings", None)
    store.data["project"].update({k: payload.get(k, "") for k in store.data["project"]})
    if isinstance(settings, dict):
        store.data["settings"].update(settings)
    store.save()
    return store.data["project"]


@app.post("/api/economic/limit")
async def upload_limit(file: UploadFile = File(...)) -> dict[str, Any]:
    raw = await file.read()
    path = store.save_upload("economic", file.filename or "limit.xlsx", raw)
    store.data["economic"]["limit"] = {"filename": file.filename, "path": str(path)}
    store.save()
    return store.data["economic"]["limit"]


@app.post("/api/economic/bidder")
async def upload_eco_bidder(name: str = Form(...), file: UploadFile = File(...)) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise HTTPException(400, "请填写投标人名称")
    raw = await file.read()
    path = store.save_upload("economic", file.filename or "bid.xlsx", raw)
    row = {"id": path.stem.split("_")[0], "name": name, "filename": file.filename, "path": str(path)}
    store.data["economic"]["bidders"].append(row)
    store.save()
    return row


@app.delete("/api/economic/bidder/{bidder_id}")
async def delete_eco_bidder(bidder_id: str) -> dict[str, Any]:
    store.data["economic"]["bidders"] = [b for b in store.data["economic"]["bidders"] if b["id"] != bidder_id]
    store.save()
    return {"ok": True}


@app.post("/api/technical/bidder")
async def upload_tech_bidder(name: str = Form(...), file: UploadFile = File(...)) -> dict[str, Any]:
    name = name.strip()
    if not name:
        raise HTTPException(400, "请填写投标人名称")
    raw = await file.read()
    path = store.save_upload("technical", file.filename or "tech.docx", raw)
    row = {"id": path.stem.split("_")[0], "name": name, "filename": file.filename, "path": str(path)}
    store.data["technical"]["bidders"].append(row)
    store.save()
    return row


@app.delete("/api/technical/bidder/{bidder_id}")
async def delete_tech_bidder(bidder_id: str) -> dict[str, Any]:
    store.data["technical"]["bidders"] = [b for b in store.data["technical"]["bidders"] if b["id"] != bidder_id]
    store.save()
    return {"ok": True}


def _price_settings() -> tuple[float, float]:
    pct = float(store.data.get("settings", {}).get("similar_price_pct") or 0.5) / 100.0
    return pct, 0.01


@app.post("/api/economic/analyze")
async def analyze_economic() -> dict[str, Any]:
    eco = store.data["economic"]
    if not eco.get("limit"):
        raise HTTPException(400, "请先上传最高投标限价 Excel")
    if len(eco.get("bidders") or []) < MIN_BIDDERS:
        raise HTTPException(400, f"经济标至少上传 {MIN_BIDDERS} 家投标人附件")
    similar_pct, abs_tol = _price_settings()
    limit = parse_excel_bid(Path(eco["limit"]["path"]), "最高投标限价")
    books = [parse_excel_bid(Path(b["path"]), b["name"]) for b in eco["bidders"]]
    findings = compare_to_limit(limit, books, similar_pct=similar_pct, abs_tol=abs_tol)
    findings.extend(cross_compare_prices(books, similar_pct=similar_pct, abs_tol=abs_tol))
    meta_entries = [
        {"bidder": "最高投标限价", "filename": eco["limit"]["filename"], "props": extract_file_properties(Path(eco["limit"]["path"]))}
    ] + [
        {"bidder": b["name"], "filename": b["filename"], "props": extract_file_properties(Path(b["path"]))}
        for b in eco["bidders"]
    ]
    meta = compare_file_properties(meta_entries)
    result = {
        "bidders": [b["name"] for b in eco["bidders"]],
        "limit_file": eco["limit"]["filename"],
        "limit_items": len(limit.items),
        "parsed": [{"bidder": b.bidder, "items": len(b.items)} for b in books],
        "findings": findings,
        "metadata": meta,
        "meta_entries": meta_entries,
    }
    store.data.setdefault("results", {})["economic"] = result
    store.save()
    return result


@app.post("/api/technical/analyze")
async def analyze_technical() -> dict[str, Any]:
    tech = store.data["technical"]
    profile = store.data["project"]
    if not (profile.get("structure") and profile.get("floors") and profile.get("area")):
        raise HTTPException(400, "请先填写基本概况：层数、建筑面积、结构类型")
    if len(tech.get("bidders") or []) < MIN_BIDDERS:
        raise HTTPException(400, f"技术标至少上传 {MIN_BIDDERS} 家投标人附件")
    threshold = float(store.data.get("settings", {}).get("text_similar_pct") or 86) / 100.0
    single: list[dict[str, Any]] = []
    docs: list[dict[str, Any]] = []
    meta_entries = []
    for b in tech["bidders"]:
        path = Path(b["path"])
        try:
            text = extract_text(path)
        except Exception as exc:
            single.append(
                {
                    "module": "技术标",
                    "bidder": b["name"],
                    "category": "无法读取文件",
                    "severity": "高",
                    "detail": str(exc),
                }
            )
            continue
        issues = validate_one(text, profile)
        for it in issues:
            it["bidder"] = b["name"]
        single.extend(issues)
        docs.append({"bidder": b["name"], "text": text, "paragraphs": split_paragraphs(text)})
        meta_entries.append({"bidder": b["name"], "filename": b["filename"], "props": extract_file_properties(path)})
    cross = cross_similar(docs, threshold=threshold)
    meta = compare_file_properties(meta_entries)
    result = {
        "bidders": [b["name"] for b in tech["bidders"]],
        "single": single,
        "cross": cross,
        "metadata": meta,
        "meta_entries": meta_entries,
    }
    store.data.setdefault("results", {})["technical"] = result
    store.save()
    return result


@app.post("/api/report")
async def make_report() -> dict[str, Any]:
    results = store.data.get("results") or {}
    eco = results.get("economic") or {}
    tech = results.get("technical") or {}
    meta = list(eco.get("metadata") or []) + list(tech.get("metadata") or [])
    path = build_report(store.data["project"], {"economic": eco, "technical": tech, "metadata": meta})
    store.data.setdefault("results", {})["report_path"] = str(path)
    store.save()
    return {"path": str(path), "filename": path.name}


@app.get("/api/report/download")
async def download_report() -> FileResponse:
    path = (store.data.get("results") or {}).get("report_path")
    if not path or not Path(path).exists():
        raise HTTPException(400, "请先生成报告")
    return FileResponse(path, filename="清标报告.docx", media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
