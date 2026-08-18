from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from jindu import __app_name__, __version__
from jindu.config import DEFAULT_PORT, STATIC_DIR, ensure_dirs
from jindu.engine.excel import content_disposition, download_name, export_xlsx
from jindu.engine.image import export_png
from jindu.engine.schedule import (
    add_log,
    add_task,
    cascade_schedule,
    empty_project,
    instantiate_template,
    load_templates,
    parse_date,
)
from jindu.store import attach_stats, get_project, load_workspace, save_workspace

app = FastAPI(title=__app_name__, version=__version__)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class WorkspaceBody(BaseModel):
    active_id: str = ""
    projects: list[dict[str, Any]] = Field(default_factory=list)


class TemplateBody(BaseModel):
    template_id: str
    name: str = ""
    location: str = ""
    manager: str = ""
    contract_start: str = ""
    demo_progress: bool = False


class LogBody(BaseModel):
    date: str = ""
    weather: str = "晴"
    temperature: str = ""
    work: str = ""
    issues: str = ""
    tomorrow: str = ""
    manpower: str = ""
    author: str = ""
    task_updates: list[dict[str, Any]] = Field(default_factory=list)


class TaskBody(BaseModel):
    name: str = "新工作"
    wbs: str = ""
    parent_id: str = ""
    planned_start: str = ""
    planned_end: str = ""
    duration: int = 7
    owner: str = ""
    progress: int = 0
    predecessor_ids: list[str] = Field(default_factory=list)
    notes: str = ""


def _today() -> date:
    return date.today()


def _project(data: dict[str, Any], project_id: str) -> dict[str, Any]:
    try:
        return get_project(data, project_id)
    except KeyError as exc:
        raise HTTPException(404, "未找到工程") from exc


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": DEFAULT_PORT}


@app.get("/api/templates")
async def templates() -> dict[str, Any]:
    items = load_templates()
    return {"templates": [{"id": t["id"], "name": t["name"], "specialty": t.get("specialty"), "notes": t.get("notes"), "task_count": len(t["tasks"])} for t in items]}


@app.get("/api/workspace")
async def workspace() -> dict[str, Any]:
    ensure_dirs()
    return load_workspace(_today())


@app.put("/api/workspace")
async def put_workspace(body: WorkspaceBody) -> dict[str, Any]:
    saved = save_workspace(body.model_dump())
    return attach_stats(saved, _today())


@app.post("/api/projects/from-template")
async def from_template(body: TemplateBody) -> dict[str, Any]:
    start = parse_date(body.contract_start) or _today()
    try:
        project = instantiate_template(
            body.template_id,
            name=body.name,
            contract_start=start,
            location=body.location,
            manager=body.manager,
            today=_today(),
            demo_progress=body.demo_progress,
        )
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = load_workspace(_today())
    data["projects"].append(project)
    data["active_id"] = project["id"]
    save_workspace(data)
    return attach_stats(data, _today())


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


@app.post("/api/projects/{project_id}/reschedule")
async def reschedule(project_id: str) -> dict[str, Any]:
    data = load_workspace(_today())
    project = _project(data, project_id)
    start = parse_date(project.get("contract_start")) or _today()
    project["tasks"] = cascade_schedule(project.get("tasks") or [], start)
    ends = [parse_date(t.get("planned_end")) for t in project["tasks"]]
    ends = [d for d in ends if d]
    if ends:
        project["contract_end"] = max(ends).isoformat()
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/tasks")
async def create_task(project_id: str, body: TaskBody) -> dict[str, Any]:
    data = load_workspace(_today())
    project = _project(data, project_id)
    add_task(project, body.model_dump())
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/logs")
async def create_log(project_id: str, body: LogBody) -> dict[str, Any]:
    data = load_workspace(_today())
    project = _project(data, project_id)
    add_log(project, body.model_dump())
    save_workspace(data)
    return attach_stats(data, _today())


@app.get("/api/projects/{project_id}/export.xlsx")
async def download_xlsx(project_id: str) -> Response:
    data = load_workspace(_today())
    project = _project(data, project_id)
    content = export_xlsx(project, _today())
    filename = download_name(project, "xlsx")
    return Response(
        content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": content_disposition(filename)},
    )


@app.get("/api/projects/{project_id}/export.png")
async def download_png(project_id: str) -> Response:
    data = load_workspace(_today())
    project = _project(data, project_id)
    content = export_png(project, _today())
    filename = download_name(project, "png")
    return Response(content, media_type="image/png", headers={"Content-Disposition": content_disposition(filename)})
