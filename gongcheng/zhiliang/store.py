from __future__ import annotations

import json
from datetime import date
from typing import Any

from zhiliang.config import DATA_DIR, WORKSPACE_FILE, ensure_dirs
from zhiliang.engine.quality import demo_project, empty_project, enrich_project


def workspace_path():
    ensure_dirs()
    return DATA_DIR / WORKSPACE_FILE


def default_workspace(today: date | None = None) -> dict[str, Any]:
    demo = demo_project(today)
    blank = empty_project("空白工程", today)
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
        "projects": [_strip(p) for p in data.get("projects") or []],
    }
    workspace_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def _strip(project: dict[str, Any]) -> dict[str, Any]:
    keep_proj = {
        "id", "name", "location", "manager", "qc_lead", "supervisor",
        "specialty", "notes", "issues", "inspections",
    }
    drop_issue = {
        "overdue", "overdue_days", "remain_days", "closed", "loop_step", "loop_label", "stats",
    }
    out = {k: project.get(k) for k in keep_proj}
    out["issues"] = [{k: v for k, v in (i or {}).items() if k not in drop_issue} for i in project.get("issues") or []]
    out["inspections"] = project.get("inspections") or []
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
