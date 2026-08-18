from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from anquan import __app_name__, __version__
from anquan.config import DEFAULT_PORT, STATIC_DIR, ensure_dirs
from anquan.engine.excel import content_disposition, download_name, export_xlsx
from anquan.engine.safety import add_hazard, add_inspection, empty_project, load_catalog, set_status
from anquan.store import attach_stats, get_project, load_workspace, save_workspace

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class WorkspaceBody(BaseModel):
    active_id: str = ""
    projects: list[dict[str, Any]] = Field(default_factory=list)


class HazardBody(BaseModel):
    template_id: str = ""
    defect_id: str = ""
    title: str = ""
    category: str = ""
    location: str = ""
    severity: str = ""
    source: str = "日常巡查"
    found_date: str = ""
    deadline: str = ""
    inspector: str = ""
    owner: str = ""
    description: str = ""
    standard: str = ""
    actual: str = ""
    allowed: str = ""
    deviation: str = ""
    cause_man: str = ""
    cause_machine: str = ""
    cause_material: str = ""
    cause_method: str = ""
    cause_env: str = ""
    corrective: str = ""
    preventive: str = ""
    rectify_plan: str = ""
    stop_work: bool = False
    notes: str = ""


class StatusBody(BaseModel):
    status: str
    rectify_plan: str = ""
    rectify_desc: str = ""
    rectify_done_date: str = ""
    review_date: str = ""
    reviewer: str = ""
    review_result: str = ""


class InspectBody(BaseModel):
    date: str = ""
    kind: str = "日检"
    area: str = ""
    inspector: str = ""
    result: str = "合格"
    findings: str = ""
    follow_up: str = ""


def _today() -> date:
    return date.today()


def _project(data: dict[str, Any], project_id: str) -> dict[str, Any]:
    try:
        return get_project(data, project_id)
    except KeyError as exc:
        raise HTTPException(404, "未找到工程") from exc


def _hazard(project: dict[str, Any], hazard_id: str) -> dict[str, Any]:
    for item in project.get("hazards") or []:
        if item["id"] == hazard_id:
            return item
    raise HTTPException(404, "未找到隐患")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": DEFAULT_PORT}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    return load_catalog()


@app.get("/api/workspace")
async def workspace() -> dict[str, Any]:
    ensure_dirs()
    return load_workspace(_today())


@app.put("/api/workspace")
async def put_workspace(body: WorkspaceBody) -> dict[str, Any]:
    return attach_stats(save_workspace(body.model_dump()), _today())


@app.post("/api/projects/empty")
async def new_empty() -> dict[str, Any]:
    data = load_workspace(_today())
    project = empty_project("新建工程", _today())
    data["projects"].append(project)
    data["active_id"] = project["id"]
    save_workspace(data)
    return attach_stats(data, _today())


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str) -> dict[str, Any]:
    data = load_workspace(_today())
    projects = [p for p in data["projects"] if p["id"] != project_id]
    if not projects:
        raise HTTPException(400, "至少保留一个工程")
    data["projects"] = projects
    if data.get("active_id") == project_id:
        data["active_id"] = projects[0]["id"]
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/hazards")
async def create_hazard(project_id: str, body: HazardBody) -> dict[str, Any]:
    data = load_workspace(_today())
    project = _project(data, project_id)
    try:
        add_hazard(project, body.model_dump(), _today())
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/hazards/{hazard_id}/status")
async def change_status(project_id: str, hazard_id: str, body: StatusBody) -> dict[str, Any]:
    data = load_workspace(_today())
    project = _project(data, project_id)
    item = _hazard(project, hazard_id)
    try:
        set_status(item, body.status, body.model_dump(), _today())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    save_workspace(data)
    return attach_stats(data, _today())


@app.delete("/api/projects/{project_id}/hazards/{hazard_id}")
async def delete_hazard(project_id: str, hazard_id: str) -> dict[str, Any]:
    data = load_workspace(_today())
    project = _project(data, project_id)
    project["hazards"] = [i for i in project.get("hazards") or [] if i["id"] != hazard_id]
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/inspections")
async def create_inspect(project_id: str, body: InspectBody) -> dict[str, Any]:
    data = load_workspace(_today())
    project = _project(data, project_id)
    add_inspection(project, body.model_dump(), _today())
    save_workspace(data)
    return attach_stats(data, _today())


@app.get("/api/projects/{project_id}/export.xlsx")
async def download_xlsx(project_id: str) -> Response:
    data = load_workspace(_today())
    project = _project(data, project_id)
    content = export_xlsx(project, _today())
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition(download_name(project))},
    )
