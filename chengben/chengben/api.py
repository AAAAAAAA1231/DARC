from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from chengben import __app_name__, __version__
from chengben.config import DEFAULT_PORT, STATIC_DIR, ensure_dirs
from chengben.engine.cost import (
    add_change,
    add_correction,
    add_item,
    add_log,
    empty_project,
    instantiate_template,
    load_catalog,
    set_corr_status,
)
from chengben.engine.excel import content_disposition, download_name, export_xlsx
from chengben.store import attach_stats, get_project, load_workspace, save_workspace

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
    cost_lead: str = ""


class ItemBody(BaseModel):
    code: str = ""
    name: str = "新科目"
    category: str = "材料费"
    unit: str = "项"
    budget_qty: float = 0
    budget_price: float = 0
    budget_amount: float = 0
    remain_amount: float | None = None
    owner: str = ""
    notes: str = ""


class LogBody(BaseModel):
    date: str = ""
    item_id: str = ""
    kind: str = "其他"
    qty: float = 0
    amount: float = 0
    voucher: str = ""
    notes: str = ""


class ChangeBody(BaseModel):
    date: str = ""
    title: str = "签证变更"
    amount: float = 0
    item_id: str = ""
    approved: bool = True
    notes: str = ""


class CorrBody(BaseModel):
    item_id: str = ""
    date: str = ""
    title: str = "成本纠偏"
    kind: str = "其他"
    deviation_amount: float = 0
    cause: str = ""
    action: str = ""
    owner: str = ""
    deadline: str = ""
    status: str = "待落实"
    notes: str = ""


class StatusBody(BaseModel):
    status: str


def _today() -> date:
    return date.today()


def _project(data: dict[str, Any], project_id: str) -> dict[str, Any]:
    try:
        return get_project(data, project_id)
    except KeyError as exc:
        raise HTTPException(404, "未找到工程") from exc


def _corr(project: dict[str, Any], corr_id: str) -> dict[str, Any]:
    for item in project.get("corrections") or []:
        if item["id"] == corr_id:
            return item
    raise HTTPException(404, "未找到纠偏记录")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health() -> dict[str, Any]:
    return {"ok": True, "app": __app_name__, "version": __version__, "offline": True, "port": DEFAULT_PORT}


@app.get("/api/catalog")
async def catalog() -> dict[str, Any]:
    data = load_catalog()
    return {
        "categories": data["categories"],
        "log_kinds": data["log_kinds"],
        "corr_kinds": data["corr_kinds"],
        "corr_statuses": data["corr_statuses"],
        "templates": [
            {"id": t["id"], "name": t["name"], "specialty": t.get("specialty"), "item_count": len(t["items"])}
            for t in data["templates"]
        ],
    }


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
    project = empty_project("新建工程")
    data["projects"].append(project)
    data["active_id"] = project["id"]
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/from-template")
async def from_template(body: TemplateBody) -> dict[str, Any]:
    try:
        project = instantiate_template(
            body.template_id, name=body.name, location=body.location, manager=body.manager, cost_lead=body.cost_lead
        )
    except KeyError as exc:
        raise HTTPException(400, str(exc)) from exc
    data = load_workspace(_today())
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


@app.post("/api/projects/{project_id}/items")
async def create_item(project_id: str, body: ItemBody) -> dict[str, Any]:
    data = load_workspace(_today())
    add_item(_project(data, project_id), body.model_dump())
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/logs")
async def create_log(project_id: str, body: LogBody) -> dict[str, Any]:
    data = load_workspace(_today())
    add_log(_project(data, project_id), body.model_dump(), _today())
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/changes")
async def create_change(project_id: str, body: ChangeBody) -> dict[str, Any]:
    data = load_workspace(_today())
    add_change(_project(data, project_id), body.model_dump(), _today())
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/corrections")
async def create_corr(project_id: str, body: CorrBody) -> dict[str, Any]:
    data = load_workspace(_today())
    add_correction(_project(data, project_id), body.model_dump(), _today())
    save_workspace(data)
    return attach_stats(data, _today())


@app.post("/api/projects/{project_id}/corrections/{corr_id}/status")
async def corr_status(project_id: str, corr_id: str, body: StatusBody) -> dict[str, Any]:
    data = load_workspace(_today())
    project = _project(data, project_id)
    try:
        set_corr_status(_corr(project, corr_id), body.status)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
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
