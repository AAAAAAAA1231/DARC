from __future__ import annotations

import copy
import json
import uuid
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from jindu.config import RESOURCES


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    if not text:
        return None
    return date.fromisoformat(text)


def iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def inclusive_days(start: date, end: date) -> int:
    if end < start:
        return 1
    return (end - start).days + 1


def add_duration(start: date, days: int) -> date:
    return start + timedelta(days=max(int(days or 1), 1) - 1)


def clamp_progress(value: Any) -> int:
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        n = 0
    return max(0, min(100, n))


def new_id(prefix: str = "t") -> str:
    return prefix + uuid.uuid4().hex[:8]


def load_templates() -> list[dict[str, Any]]:
    path = RESOURCES / "templates.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["templates"]


def get_template(template_id: str) -> dict[str, Any]:
    for item in load_templates():
        if item["id"] == template_id:
            return item
    raise KeyError(f"未找到模板：{template_id}")


def _children_map(tasks: list[dict[str, Any]]) -> dict[str, list[str]]:
    mapping: dict[str, list[str]] = defaultdict(list)
    for task in tasks:
        parent = task.get("parent_id") or ""
        if parent:
            mapping[parent].append(task["id"])
    return mapping


def is_summary(task: dict[str, Any], children: dict[str, list[str]]) -> bool:
    return bool(task.get("summary")) or bool(children.get(task["id"]))


def _pred_ids(task: dict[str, Any]) -> list[str]:
    raw = task.get("predecessor_ids") or []
    if isinstance(raw, str):
        raw = [p.strip() for p in raw.replace("，", ",").split(",") if p.strip()]
    return [str(p) for p in raw if p]


def cascade_schedule(tasks: list[dict[str, Any]], project_start: date) -> list[dict[str, Any]]:
    """Fill planned_start / planned_end from duration, offset, and FS predecessors."""
    items = copy.deepcopy(tasks)
    by_id = {t["id"]: t for t in items}
    children = _children_map(items)
    done: set[str] = set()
    guard = 0
    pending = [t for t in items if not is_summary(t, children)]
    while pending and guard < 8000:
        guard += 1
        progressed = False
        for task in list(pending):
            preds = [by_id[p] for p in _pred_ids(task) if p in by_id]
            if any(p["id"] not in done for p in preds):
                continue
            starts: list[date] = []
            offset = int(task.get("offset") or 0)
            if preds:
                for pred in preds:
                    end = parse_date(pred.get("planned_end"))
                    if end is None:
                        continue
                    lag = int(task.get("lag_days") or 0)
                    starts.append(end + timedelta(days=1 + lag))
            else:
                starts.append(project_start + timedelta(days=offset))
            if not starts:
                continue
            start = max(starts)
            duration = int(task.get("duration") or 1)
            task["planned_start"] = iso(start)
            task["planned_end"] = iso(add_duration(start, duration))
            task["duration"] = duration
            done.add(task["id"])
            pending.remove(task)
            progressed = True
        if not progressed:
            # leftover cycles or missing preds: pin to project start
            for task in pending:
                start = project_start + timedelta(days=int(task.get("offset") or 0))
                duration = int(task.get("duration") or 1)
                task["planned_start"] = iso(start)
                task["planned_end"] = iso(add_duration(start, duration))
                done.add(task["id"])
            break
    _rollup_summaries(items, children)
    return items


def _rollup_summaries(tasks: list[dict[str, Any]], children: dict[str, list[str]]) -> None:
    by_id = {t["id"]: t for t in tasks}

    def walk(task_id: str) -> tuple[date | None, date | None]:
        kids = children.get(task_id) or []
        if not kids:
            task = by_id[task_id]
            return parse_date(task.get("planned_start")), parse_date(task.get("planned_end"))
        starts: list[date] = []
        ends: list[date] = []
        for kid in kids:
            s, e = walk(kid)
            if s:
                starts.append(s)
            if e:
                ends.append(e)
        task = by_id[task_id]
        start = min(starts) if starts else parse_date(task.get("planned_start"))
        end = max(ends) if ends else parse_date(task.get("planned_end"))
        if start and end:
            task["planned_start"] = iso(start)
            task["planned_end"] = iso(end)
            task["duration"] = inclusive_days(start, end)
            task["summary"] = True
        return start, end

    roots = [t["id"] for t in tasks if not t.get("parent_id")]
    for rid in roots:
        walk(rid)


def _leaf_progress(task: dict[str, Any], children: dict[str, list[str]], by_id: dict[str, dict[str, Any]]) -> float:
    kids = children.get(task["id"]) or []
    if not kids:
        return float(clamp_progress(task.get("progress")))
    weighted = 0.0
    total = 0.0
    for kid_id in kids:
        child = by_id[kid_id]
        dur = max(int(child.get("duration") or 1), 1)
        weighted += _leaf_progress(child, children, by_id) * dur
        total += dur
    pct = weighted / total if total else 0.0
    task["progress"] = int(round(pct))
    return pct


def _planned_pct(start: date | None, end: date | None, today: date) -> int:
    if not start or not end:
        return 0
    if today < start:
        return 0
    if today >= end:
        return 100
    return int(round(100 * (today - start).days / max((end - start).days, 1)))


def _status(task: dict[str, Any], today: date) -> str:
    progress = clamp_progress(task.get("progress"))
    planned_start = parse_date(task.get("planned_start"))
    planned_end = parse_date(task.get("planned_end"))
    actual_end = parse_date(task.get("actual_end"))
    if progress >= 100 or actual_end:
        if planned_end and actual_end and actual_end > planned_end:
            return "延期完成"
        return "已完成"
    delayed = False
    if planned_end and today > planned_end and progress < 100:
        delayed = True
    if planned_start and today > planned_start and progress == 0:
        delayed = True
    if delayed:
        return "滞后"
    if progress > 0 or parse_date(task.get("actual_start")):
        return "进行中"
    return "未开始"


def _delayed_days(task: dict[str, Any], today: date) -> int:
    progress = clamp_progress(task.get("progress"))
    planned_end = parse_date(task.get("planned_end"))
    actual_end = parse_date(task.get("actual_end"))
    if progress >= 100:
        if planned_end and actual_end and actual_end > planned_end:
            return (actual_end - planned_end).days
        return 0
    if planned_end and today > planned_end:
        return (today - planned_end).days
    planned_start = parse_date(task.get("planned_start"))
    if planned_start and today > planned_start and progress == 0:
        return (today - planned_start).days
    return 0


def compute_cpm(tasks: list[dict[str, Any]]) -> None:
    """Forward / backward pass on leaf tasks. Summaries inherit from children."""
    children = _children_map(tasks)
    by_id = {t["id"]: t for t in tasks}
    leaves = [t for t in tasks if not is_summary(t, children)]
    if not leaves:
        return
    preds = {t["id"]: [p for p in _pred_ids(t) if p in by_id] for t in leaves}
    succs: dict[str, list[str]] = defaultdict(list)
    for tid, plist in preds.items():
        for p in plist:
            succs[p].append(tid)

    # Forward
    remaining = set(t["id"] for t in leaves)
    es_map: dict[str, date] = {}
    ef_map: dict[str, date] = {}
    guard = 0
    while remaining and guard < 8000:
        guard += 1
        ready = []
        for tid in list(remaining):
            if all(p not in remaining for p in preds[tid]):
                ready.append(tid)
        if not ready:
            for tid in list(remaining):
                task = by_id[tid]
                start = parse_date(task.get("planned_start"))
                end = parse_date(task.get("planned_end"))
                if start and end:
                    es_map[tid] = start
                    ef_map[tid] = end
                remaining.discard(tid)
            break
        for tid in ready:
            task = by_id[tid]
            start = parse_date(task.get("planned_start"))
            end = parse_date(task.get("planned_end"))
            if preds[tid]:
                ends = [ef_map[p] for p in preds[tid] if p in ef_map]
                if ends:
                    cand = max(ends) + timedelta(days=1 + int(task.get("lag_days") or 0))
                    start = cand if start is None else start
            if start is None or end is None:
                remaining.discard(tid)
                continue
            es_map[tid] = start
            ef_map[tid] = end
            remaining.discard(tid)

    if not ef_map:
        return
    project_end = max(ef_map.values())

    # Backward
    remaining = set(es_map)
    ls_map: dict[str, date] = {}
    lf_map: dict[str, date] = {}
    guard = 0
    while remaining and guard < 8000:
        guard += 1
        ready = [tid for tid in remaining if all(s not in remaining for s in succs.get(tid, []) if s in es_map)]
        if not ready:
            break
        for tid in ready:
            task = by_id[tid]
            start = es_map[tid]
            end = ef_map[tid]
            dur = inclusive_days(start, end)
            child_succs = [s for s in succs.get(tid, []) if s in ls_map]
            if child_succs:
                lf = min(ls_map[s] - timedelta(days=1) for s in child_succs)
            else:
                lf = project_end
            ls = lf - timedelta(days=dur - 1)
            ls_map[tid] = ls
            lf_map[tid] = lf
            remaining.discard(tid)

    for task in leaves:
        tid = task["id"]
        if tid not in es_map or tid not in ls_map:
            task["float_days"] = 0
            task["critical"] = False
            continue
        float_days = (ls_map[tid] - es_map[tid]).days
        task["es"] = iso(es_map[tid])
        task["ef"] = iso(ef_map[tid])
        task["ls"] = iso(ls_map[tid])
        task["lf"] = iso(lf_map[tid])
        task["float_days"] = float_days
        task["critical"] = float_days <= 0


def enrich_project(project: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    data = copy.deepcopy(project)
    today = today or date.today()
    tasks = data.get("tasks") or []
    children = _children_map(tasks)
    by_id = {t["id"]: t for t in tasks}
    compute_cpm(tasks)
    children = _children_map(tasks)
    by_id = {t["id"]: t for t in tasks}

    starts: list[date] = []
    ends: list[date] = []
    leaf_weight = 0.0
    leaf_done = 0.0
    delayed = 0
    critical = 0
    for task in tasks:
        ps, pe = parse_date(task.get("planned_start")), parse_date(task.get("planned_end"))
        if ps and pe:
            task["duration"] = inclusive_days(ps, pe)
            starts.append(ps)
            ends.append(pe)
        if is_summary(task, children):
            _leaf_progress(task, children, by_id)
        task["progress"] = clamp_progress(task.get("progress"))
        task["status"] = _status(task, today)
        task["delayed_days"] = _delayed_days(task, today)
        task["planned_pct"] = _planned_pct(ps, pe, today)
        task["summary"] = is_summary(task, children)
        if not task["summary"]:
            dur = max(int(task.get("duration") or 1), 1)
            leaf_weight += dur
            leaf_done += task["progress"] * dur / 100.0
            if task["status"] == "滞后":
                delayed += 1
            if task.get("critical"):
                critical += 1

    overall = int(round(100 * leaf_done / leaf_weight)) if leaf_weight else 0
    pstart = min(starts) if starts else parse_date(data.get("contract_start"))
    pend = max(ends) if ends else parse_date(data.get("contract_end"))
    planned_overall = _planned_pct(pstart, pend, today)
    spi = round(overall / planned_overall, 2) if planned_overall else 1.0
    remain = (pend - today).days if pend else 0
    data["stats"] = {
        "today": iso(today),
        "overall": overall,
        "planned_overall": planned_overall,
        "spi": spi,
        "delayed_count": delayed,
        "critical_count": critical,
        "task_count": len(tasks),
        "leaf_count": sum(1 for t in tasks if not t.get("summary")),
        "remaining_days": remain,
        "range_start": iso(pstart),
        "range_end": iso(pend),
    }
    return data


def instantiate_template(
    template_id: str,
    *,
    name: str,
    contract_start: date,
    location: str = "",
    manager: str = "",
    today: date | None = None,
    demo_progress: bool = False,
) -> dict[str, Any]:
    tmpl = get_template(template_id)
    key_to_id: dict[str, str] = {}
    raw_tasks = tmpl["tasks"]
    for row in raw_tasks:
        key_to_id[row["key"]] = new_id()
    tasks: list[dict[str, Any]] = []
    for row in raw_tasks:
        parent_key = row.get("parent") or ""
        tasks.append(
            {
                "id": key_to_id[row["key"]],
                "parent_id": key_to_id.get(parent_key, ""),
                "wbs": row["wbs"],
                "name": row["name"],
                "duration": int(row.get("duration") or 1),
                "offset": int(row.get("offset") or 0),
                "lag_days": int(row.get("lag_days") or 0),
                "predecessor_ids": [key_to_id[k] for k in (row.get("pred") or []) if k in key_to_id],
                "owner": row.get("owner") or "",
                "progress": 0,
                "planned_start": "",
                "planned_end": "",
                "actual_start": "",
                "actual_end": "",
                "notes": row.get("notes") or "",
                "summary": bool(row.get("summary")),
            }
        )
    tasks = cascade_schedule(tasks, contract_start)
    last_end = max((parse_date(t["planned_end"]) for t in tasks if parse_date(t.get("planned_end"))), default=contract_start)
    project = {
        "id": new_id("p"),
        "name": name or tmpl["name"],
        "location": location,
        "manager": manager,
        "specialty": tmpl.get("specialty") or "",
        "template_id": template_id,
        "contract_start": iso(contract_start),
        "contract_end": iso(last_end),
        "tasks": tasks,
        "logs": [],
        "notes": tmpl.get("notes") or "",
    }
    if demo_progress:
        project["tasks"] = apply_time_progress(project["tasks"], today or date.today())
    return enrich_project(project, today)


def apply_time_progress(tasks: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """Fill a realistic as-of-today progress for demo / first-run data."""
    items = copy.deepcopy(tasks)
    children = _children_map(items)
    delayed_once = False
    for task in items:
        if is_summary(task, children):
            continue
        start = parse_date(task.get("planned_start"))
        end = parse_date(task.get("planned_end"))
        if not start or not end:
            continue
        pct = _planned_pct(start, end, today)
        if pct > 0:
            task["actual_start"] = iso(start)
        if pct >= 100:
            task["progress"] = 100
            task["actual_end"] = iso(end)
        elif pct > 0:
            slip = 18 if not delayed_once and pct > 30 else 0
            if slip:
                delayed_once = True
            task["progress"] = max(5, pct - slip)
        else:
            task["progress"] = 0
    return items


def empty_project(name: str = "新建工程", start: date | None = None) -> dict[str, Any]:
    start = start or date.today()
    return {
        "id": new_id("p"),
        "name": name,
        "location": "",
        "manager": "",
        "specialty": "",
        "template_id": "",
        "contract_start": iso(start),
        "contract_end": iso(start + timedelta(days=179)),
        "tasks": [],
        "logs": [],
        "notes": "",
    }


def add_task(project: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    tasks = project.setdefault("tasks", [])
    start = parse_date(payload.get("planned_start")) or parse_date(project.get("contract_start")) or date.today()
    duration = int(payload.get("duration") or 7)
    end = parse_date(payload.get("planned_end")) or add_duration(start, duration)
    wbs = str(payload.get("wbs") or _next_wbs(tasks, payload.get("parent_id") or ""))
    task = {
        "id": new_id(),
        "parent_id": payload.get("parent_id") or "",
        "wbs": wbs,
        "name": payload.get("name") or "新工作",
        "duration": inclusive_days(start, end),
        "offset": 0,
        "lag_days": int(payload.get("lag_days") or 0),
        "predecessor_ids": payload.get("predecessor_ids") or [],
        "owner": payload.get("owner") or "",
        "progress": clamp_progress(payload.get("progress")),
        "planned_start": iso(start),
        "planned_end": iso(end),
        "actual_start": payload.get("actual_start") or "",
        "actual_end": payload.get("actual_end") or "",
        "notes": payload.get("notes") or "",
        "summary": False,
    }
    tasks.append(task)
    return task


def _next_wbs(tasks: list[dict[str, Any]], parent_id: str) -> str:
    if parent_id:
        parent = next((t for t in tasks if t["id"] == parent_id), None)
        prefix = (parent or {}).get("wbs") or "1"
        n = 1 + sum(1 for t in tasks if t.get("parent_id") == parent_id)
        return f"{prefix}.{n}"
    tops = []
    for task in tasks:
        if task.get("parent_id"):
            continue
        try:
            tops.append(int(str(task.get("wbs") or "0").split(".")[0]))
        except ValueError:
            continue
    return str((max(tops) if tops else 0) + 1)


def add_log(project: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "id": new_id("l"),
        "date": payload.get("date") or iso(date.today()),
        "weather": payload.get("weather") or "晴",
        "temperature": payload.get("temperature") or "",
        "work": payload.get("work") or "",
        "issues": payload.get("issues") or "",
        "tomorrow": payload.get("tomorrow") or "",
        "manpower": payload.get("manpower") or "",
        "author": payload.get("author") or project.get("manager") or "",
    }
    logs = project.setdefault("logs", [])
    logs.insert(0, entry)
    updates = payload.get("task_updates") or []
    by_id = {t["id"]: t for t in project.get("tasks") or []}
    for upd in updates:
        task = by_id.get(upd.get("task_id"))
        if not task:
            continue
        if "progress" in upd:
            task["progress"] = clamp_progress(upd["progress"])
        if upd.get("actual_start"):
            task["actual_start"] = upd["actual_start"]
        if upd.get("actual_end"):
            task["actual_end"] = upd["actual_end"]
        if task["progress"] > 0 and not task.get("actual_start"):
            task["actual_start"] = entry["date"]
        if task["progress"] >= 100 and not task.get("actual_end"):
            task["actual_end"] = entry["date"]
    return entry
