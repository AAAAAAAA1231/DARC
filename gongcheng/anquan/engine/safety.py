from __future__ import annotations

import copy
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from anquan.config import RESOURCES

STATUSES = ("待整改", "整改中", "待复查", "已闭合")


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


def new_id(prefix: str = "h") -> str:
    return prefix + uuid.uuid4().hex[:8]


def load_catalog() -> dict[str, Any]:
    return json.loads((RESOURCES / "catalog.json").read_text(encoding="utf-8"))


def get_template(template_id: str) -> dict[str, Any]:
    for item in load_catalog()["hazards"]:
        if item["id"] == template_id:
            return item
    raise KeyError(f"未找到隐患模板：{template_id}")


def next_no(project: dict[str, Any], today: date | None = None) -> str:
    today = today or date.today()
    prefix = f"YH-{today.year}-"
    nums: list[int] = []
    for item in project.get("hazards") or []:
        no = str(item.get("no") or "")
        if no.startswith(prefix):
            tail = no[len(prefix):]
            if tail.isdigit():
                nums.append(int(tail))
    return f"{prefix}{(max(nums) if nums else 0) + 1:03d}"


def _flags(item: dict[str, Any], today: date) -> dict[str, Any]:
    status = item.get("status") or "待整改"
    if status not in STATUSES:
        status = "待整改"
    deadline = parse_date(item.get("deadline"))
    closed = status == "已闭合"
    overdue = False
    overdue_days = 0
    remain_days: int | None = None
    if not closed and deadline:
        remain_days = (deadline - today).days
        if remain_days < 0:
            overdue = True
            overdue_days = -remain_days
    if status == "待整改":
        step = 0
    elif status == "整改中":
        step = 1
    elif status == "待复查":
        step = 2
    else:
        step = 3
    major = (item.get("severity") or "") == "重大隐患"
    return {
        "status": status,
        "overdue": overdue,
        "overdue_days": overdue_days,
        "remain_days": remain_days,
        "closed": closed,
        "loop_step": step,
        "loop_label": ["发现", "整改", "复查", "闭合"][step],
        "stop_work": bool(item.get("stop_work") or (major and not closed)),
    }


def enrich_project(project: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    data = copy.deepcopy(project)
    today = today or date.today()
    hazards = data.get("hazards") or []
    open_n = overdue_n = major_n = closed_week = new_week = stop_n = 0
    by_cat: dict[str, int] = {}
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    week_ago = today - timedelta(days=7)
    for item in hazards:
        flags = _flags(item, today)
        item.update(flags)
        cat = item.get("category") or "其他"
        by_cat[cat] = by_cat.get(cat, 0) + 1
        by_status[item["status"]] = by_status.get(item["status"], 0) + 1
        if not item["closed"]:
            open_n += 1
        if item["overdue"]:
            overdue_n += 1
        if item.get("severity") == "重大隐患" and not item["closed"]:
            major_n += 1
        if item.get("stop_work") and not item["closed"]:
            stop_n += 1
        found = parse_date(item.get("found_date"))
        closed_at = parse_date(item.get("review_date")) if item["closed"] else None
        if found and found >= week_ago:
            new_week += 1
        if closed_at and closed_at >= week_ago:
            closed_week += 1
    data["stats"] = {
        "today": iso(today),
        "hazard_count": len(hazards),
        "open_count": open_n,
        "overdue_count": overdue_n,
        "major_open": major_n,
        "stop_count": stop_n,
        "new_week": new_week,
        "closed_week": closed_week,
        "inspect_count": len(data.get("inspections") or []),
        "by_category": by_cat,
        "by_status": by_status,
        "close_rate": int(round(100 * by_status.get("已闭合", 0) / len(hazards))) if hazards else 100,
    }
    return data


def empty_project(name: str = "新建工程", today: date | None = None) -> dict[str, Any]:
    return {
        "id": new_id("p"),
        "name": name,
        "location": "",
        "manager": "",
        "safety_lead": "",
        "supervisor": "",
        "specialty": "房屋建筑",
        "notes": "",
        "hazards": [],
        "inspections": [],
    }


def _blank_hazard(project: dict[str, Any], payload: dict[str, Any], today: date) -> dict[str, Any]:
    found = parse_date(payload.get("found_date")) or today
    deadline = parse_date(payload.get("deadline"))
    if deadline is None:
        days = 1 if payload.get("severity") == "重大隐患" else 7
        deadline = found + timedelta(days=int(payload.get("days") or days))
    return {
        "id": new_id("h"),
        "no": next_no(project, today),
        "title": payload.get("title") or "安全隐患",
        "template_id": payload.get("template_id") or payload.get("defect_id") or "",
        "category": payload.get("category") or "高处作业",
        "location": payload.get("location") or "",
        "severity": payload.get("severity") or "一般隐患",
        "source": payload.get("source") or "日常巡查",
        "found_date": iso(found),
        "deadline": iso(deadline),
        "inspector": payload.get("inspector") or "",
        "owner": payload.get("owner") or "",
        "status": payload.get("status") or "待整改",
        "stop_work": bool(payload.get("stop_work")),
        "description": payload.get("description") or "",
        "standard": payload.get("standard") or "",
        "actual": payload.get("actual") or "",
        "allowed": payload.get("allowed") or "",
        "deviation": payload.get("deviation") or "",
        "cause_man": payload.get("cause_man") or "",
        "cause_machine": payload.get("cause_machine") or "",
        "cause_material": payload.get("cause_material") or "",
        "cause_method": payload.get("cause_method") or "",
        "cause_env": payload.get("cause_env") or "",
        "corrective": payload.get("corrective") or "",
        "preventive": payload.get("preventive") or "",
        "rectify_plan": payload.get("rectify_plan") or "",
        "rectify_desc": payload.get("rectify_desc") or "",
        "rectify_done_date": payload.get("rectify_done_date") or "",
        "review_date": payload.get("review_date") or "",
        "reviewer": payload.get("reviewer") or "",
        "review_result": payload.get("review_result") or "",
        "notes": payload.get("notes") or "",
    }


def add_hazard(project: dict[str, Any], payload: dict[str, Any] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    payload = dict(payload or {})
    tid = payload.get("template_id") or payload.get("defect_id") or ""
    if tid:
        tmpl = get_template(tid)
        for key, value in (
            ("title", tmpl["name"]),
            ("category", tmpl["category"]),
            ("severity", tmpl["severity"]),
            ("description", tmpl["description"]),
            ("standard", tmpl["standard"]),
            ("corrective", tmpl["corrective"]),
            ("preventive", tmpl["preventive"]),
            ("rectify_plan", tmpl["corrective"]),
        ):
            if not payload.get(key):
                payload[key] = value
        payload["template_id"] = tid
        if tmpl["severity"] == "重大隐患":
            payload["stop_work"] = True
    item = _blank_hazard(project, payload, today)
    project.setdefault("hazards", []).insert(0, item)
    return item


def add_inspection(project: dict[str, Any], payload: dict[str, Any] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    payload = payload or {}
    rec = {
        "id": new_id("n"),
        "date": payload.get("date") or iso(today),
        "kind": payload.get("kind") or "日检",
        "area": payload.get("area") or "",
        "inspector": payload.get("inspector") or project.get("safety_lead") or "",
        "result": payload.get("result") or "合格",
        "findings": payload.get("findings") or "",
        "follow_up": payload.get("follow_up") or "",
    }
    project.setdefault("inspections", []).insert(0, rec)
    return rec


def set_status(item: dict[str, Any], status: str, payload: dict[str, Any] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    payload = payload or {}
    if status not in STATUSES:
        raise ValueError("状态不合法")
    item["status"] = status
    if status == "整改中":
        item["rectify_plan"] = payload.get("rectify_plan") or item.get("rectify_plan") or ""
    if status == "待复查":
        item["rectify_desc"] = payload.get("rectify_desc") or item.get("rectify_desc") or ""
        item["rectify_done_date"] = payload.get("rectify_done_date") or iso(today)
    if status == "已闭合":
        item["review_date"] = payload.get("review_date") or iso(today)
        item["reviewer"] = payload.get("reviewer") or item.get("reviewer") or ""
        item["review_result"] = payload.get("review_result") or "复查合格，隐患闭合"
        item["stop_work"] = False
        if not item.get("rectify_done_date"):
            item["rectify_done_date"] = iso(today)
    return item


def demo_project(today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    project = empty_project("××小区 1# 住宅楼工程", today)
    project.update(
        {
            "location": "本市",
            "manager": "项目经理",
            "safety_lead": "安全员",
            "supervisor": "监理安全工程师",
            "notes": "示例数据，便于先看隐患闭环和纠偏。可删除后按现场重录。",
        }
    )
    samples = [
        {"template_id": "edge", "location": "7层电梯井", "owner": "木工班组长", "found_date": iso(today), "deadline": iso(today), "status": "待整改", "inspector": "安全员", "actual": "井口无翻板"},
        {"template_id": "power-三级", "location": "现场一级配电室至钢筋加工棚", "owner": "电工班", "found_date": iso(today - timedelta(days=3)), "deadline": iso(today - timedelta(days=1)), "status": "待整改", "inspector": "安全员"},
        {"template_id": "scaffold-tie", "location": "外架 5～6 层", "owner": "架子班", "found_date": iso(today - timedelta(days=8)), "deadline": iso(today - timedelta(days=6)), "status": "整改中", "inspector": "监理安全工程师", "cause_method": "为砌筑拆除连墙件未报批"},
        {"template_id": "formwork", "location": "地下室顶板高支模", "owner": "木工班", "found_date": iso(today - timedelta(days=5)), "deadline": iso(today + timedelta(days=1)), "status": "待复查", "rectify_desc": "已按方案补剪刀撑，待项目技术负责人复验", "rectify_done_date": iso(today - timedelta(days=1)), "inspector": "安全员"},
        {"template_id": "civil", "location": "东门消防通道", "owner": "材料员", "found_date": iso(today - timedelta(days=20)), "deadline": iso(today - timedelta(days=18)), "status": "已闭合", "review_date": iso(today - timedelta(days=16)), "reviewer": "安全员", "review_result": "材料已清运，通道畅通", "inspector": "安全员"},
    ]
    for row in reversed(samples):
        add_hazard(project, row, today)
    add_inspection(
        project,
        {
            "date": iso(today),
            "kind": "日检",
            "area": "主体 5～7 层及临电",
            "inspector": "安全员",
            "result": "有隐患",
            "findings": "7层电梯井无翻板；加工棚线路未做到三级配电。",
            "follow_up": "已下发隐患整改，重大隐患要求立即停用相关作业面。",
        },
        today,
    )
    add_inspection(
        project,
        {
            "date": iso(today - timedelta(days=5)),
            "kind": "危大工程巡视",
            "area": "地下室高支模",
            "inspector": "项目技术负责人",
            "result": "合格（有一般问题）",
            "findings": "剪刀撑局部偏少，已要求补设。",
            "follow_up": "列入台账，浇筑前复验。",
        },
        today,
    )
    return project
