from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any

from jindu.config import DATA_DIR, WORKSPACE_FILE, ensure_dirs
from jindu.engine.schedule import empty_project, enrich_project, instantiate_template


def workspace_path():
    ensure_dirs()
    return DATA_DIR / WORKSPACE_FILE


def default_workspace(today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    demo = instantiate_template(
        "住宅楼",
        name="××小区 1# 住宅楼工程",
        contract_start=today - timedelta(days=120),
        location="本市",
        manager="项目经理",
        today=today,
        demo_progress=True,
    )
    blank = empty_project("空白工程（可从模板重建）", today)
    return {"active_id": demo["id"], "projects": [demo, blank]}


def load_workspace(today: date | None = None) -> dict[str, Any]:
    path = workspace_path()
    if not path.exists():
        data = default_workspace(today)
        save_workspace(data)
        return attach_stats(data, today)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not raw.get("projects"):
        raw = default_workspace(today)
        save_workspace(raw)
    return attach_stats(raw, today)


def save_workspace(data: dict[str, Any]) -> dict[str, Any]:
    ensure_dirs()
    payload = {
        "active_id": data.get("active_id") or "",
        "projects": [_strip_computed(p) for p in data.get("projects") or []],
    }
    workspace_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _strip_computed(project: dict[str, Any]) -> dict[str, Any]:
    keep_task = {
        "id", "parent_id", "wbs", "name", "duration", "offset", "lag_days",
        "predecessor_ids", "owner", "progress", "planned_start", "planned_end",
        "actual_start", "actual_end", "notes", "summary",
    }
    keep_proj = {
        "id", "name", "location", "manager", "specialty", "template_id",
        "contract_start", "contract_end", "notes", "logs", "tasks",
    }
    out = {k: project.get(k) for k in keep_proj if k in project or k in ("tasks", "logs")}
    out["tasks"] = [{k: t.get(k) for k in keep_task if k in t} for t in project.get("tasks") or []]
    out["logs"] = project.get("logs") or []
    return out


def attach_stats(data: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    projects = [enrich_project(p, today) for p in data.get("projects") or []]
    active = data.get("active_id") or (projects[0]["id"] if projects else "")
    if active and all(p["id"] != active for p in projects) and projects:
        active = projects[0]["id"]
    return {"active_id": active, "projects": projects}


def get_project(data: dict[str, Any], project_id: str) -> dict[str, Any]:
    for item in data.get("projects") or []:
        if item["id"] == project_id:
            return item
    raise KeyError("未找到工程")
