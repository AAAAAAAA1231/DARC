from __future__ import annotations

import json
from datetime import date
from typing import Any

from chengben.config import DATA_DIR, WORKSPACE_FILE, ensure_dirs
from chengben.engine.cost import apply_demo_progress, empty_project, enrich_project, instantiate_template


def workspace_path():
    ensure_dirs()
    return DATA_DIR / WORKSPACE_FILE


def default_workspace(today: date | None = None) -> dict[str, Any]:
    demo = apply_demo_progress(
        instantiate_template("住宅楼", name="××小区 1# 住宅楼工程", location="本市", manager="项目经理", cost_lead="成本员"),
        today,
    )
    blank = empty_project("空白工程")
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
    drop_item = {"target", "forecast", "deviation", "deviation_rate", "flag", "qty_diff", "actual_price", "price_diff"}
    drop_corr = {"closed", "overdue"}
    keep = {
        "id", "name", "location", "manager", "cost_lead", "specialty",
        "contract_amount", "notes", "template_id", "items", "logs", "corrections", "changes",
    }
    out = {k: project.get(k) for k in keep}
    out["items"] = [{k: v for k, v in (i or {}).items() if k not in drop_item} for i in project.get("items") or []]
    out["logs"] = project.get("logs") or []
    out["corrections"] = [{k: v for k, v in (c or {}).items() if k not in drop_corr} for c in project.get("corrections") or []]
    out["changes"] = project.get("changes") or []
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
