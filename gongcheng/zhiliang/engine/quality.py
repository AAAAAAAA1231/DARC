from __future__ import annotations

import copy
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from zhiliang.config import RESOURCES

STATUSES = ("待整改", "整改中", "待复查", "已闭合")
OPEN_STATUSES = {"待整改", "整改中", "待复查"}


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


def new_id(prefix: str = "q") -> str:
    return prefix + uuid.uuid4().hex[:8]


def load_catalog() -> dict[str, Any]:
    path = RESOURCES / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def get_defect(defect_id: str) -> dict[str, Any]:
    for item in load_catalog()["defects"]:
        if item["id"] == defect_id:
            return item
    raise KeyError(f"未找到质量通病模板：{defect_id}")


def next_issue_no(project: dict[str, Any], today: date | None = None) -> str:
    today = today or date.today()
    prefix = f"ZL-{today.year}-"
    nums: list[int] = []
    for issue in project.get("issues") or []:
        no = str(issue.get("no") or "")
        if no.startswith(prefix):
            tail = no[len(prefix):]
            if tail.isdigit():
                nums.append(int(tail))
    return f"{prefix}{(max(nums) if nums else 0) + 1:03d}"


def _issue_flags(issue: dict[str, Any], today: date) -> dict[str, Any]:
    status = issue.get("status") or "待整改"
    if status not in STATUSES:
        status = "待整改"
    deadline = parse_date(issue.get("deadline"))
    closed = status == "已闭合"
    overdue = False
    overdue_days = 0
    remain_days: int | None = None
    if not closed and deadline:
        remain_days = (deadline - today).days
        if remain_days < 0:
            overdue = True
            overdue_days = -remain_days
    loop = ["发现", "整改", "复查", "闭合"]
    if status == "待整改":
        step = 0
    elif status == "整改中":
        step = 1
    elif status == "待复查":
        step = 2
    else:
        step = 3
    return {
        "status": status,
        "overdue": overdue,
        "overdue_days": overdue_days,
        "remain_days": remain_days,
        "closed": closed,
        "loop_step": step,
        "loop_label": loop[step],
    }


def enrich_project(project: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    data = copy.deepcopy(project)
    today = today or date.today()
    issues = data.get("issues") or []
    open_n = overdue_n = major_n = closed_week = new_week = 0
    by_spec: dict[str, int] = {}
    by_status: dict[str, int] = {s: 0 for s in STATUSES}
    week_ago = today - timedelta(days=7)
    for issue in issues:
        flags = _issue_flags(issue, today)
        issue.update(flags)
        spec = issue.get("specialty") or "其他"
        by_spec[spec] = by_spec.get(spec, 0) + 1
        by_status[issue["status"]] = by_status.get(issue["status"], 0) + 1
        if not issue["closed"]:
            open_n += 1
        if issue["overdue"]:
            overdue_n += 1
        if issue.get("severity") == "重大" and not issue["closed"]:
            major_n += 1
        found = parse_date(issue.get("found_date"))
        closed_at = parse_date(issue.get("review_date")) if issue["closed"] else None
        if found and found >= week_ago:
            new_week += 1
        if closed_at and closed_at >= week_ago:
            closed_week += 1
    data["stats"] = {
        "today": iso(today),
        "issue_count": len(issues),
        "open_count": open_n,
        "overdue_count": overdue_n,
        "major_open": major_n,
        "new_week": new_week,
        "closed_week": closed_week,
        "inspect_count": len(data.get("inspections") or []),
        "by_specialty": by_spec,
        "by_status": by_status,
        "close_rate": int(round(100 * by_status.get("已闭合", 0) / len(issues))) if issues else 100,
    }
    return data


def empty_project(name: str = "新建工程", today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    return {
        "id": new_id("p"),
        "name": name,
        "location": "",
        "manager": "",
        "qc_lead": "",
        "supervisor": "",
        "specialty": "房屋建筑",
        "notes": "",
        "issues": [],
        "inspections": [],
    }


def issue_from_defect(project: dict[str, Any], defect_id: str, payload: dict[str, Any] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    defect = get_defect(defect_id)
    payload = payload or {}
    found = parse_date(payload.get("found_date")) or today
    deadline = parse_date(payload.get("deadline")) or found + timedelta(days=int(payload.get("days") or 7))
    return {
        "id": new_id("i"),
        "no": next_issue_no(project, today),
        "title": payload.get("title") or defect["name"],
        "defect_id": defect_id,
        "specialty": payload.get("specialty") or defect["specialty"],
        "location": payload.get("location") or "",
        "severity": payload.get("severity") or defect["severity"],
        "source": payload.get("source") or "日常巡检",
        "found_date": iso(found),
        "deadline": iso(deadline),
        "inspector": payload.get("inspector") or "",
        "owner": payload.get("owner") or "",
        "status": payload.get("status") or "待整改",
        "description": payload.get("description") or defect["description"],
        "standard": payload.get("standard") or defect["standard"],
        "actual": payload.get("actual") or "",
        "allowed": payload.get("allowed") or "",
        "deviation": payload.get("deviation") or "",
        "cause_man": payload.get("cause_man") or "",
        "cause_machine": payload.get("cause_machine") or "",
        "cause_material": payload.get("cause_material") or "",
        "cause_method": payload.get("cause_method") or "",
        "cause_env": payload.get("cause_env") or "",
        "corrective": payload.get("corrective") or defect["corrective"],
        "preventive": payload.get("preventive") or defect["preventive"],
        "rectify_plan": payload.get("rectify_plan") or defect["corrective"],
        "rectify_desc": payload.get("rectify_desc") or "",
        "rectify_done_date": payload.get("rectify_done_date") or "",
        "review_date": payload.get("review_date") or "",
        "reviewer": payload.get("reviewer") or "",
        "review_result": payload.get("review_result") or "",
        "notes": payload.get("notes") or "",
    }


def add_issue(project: dict[str, Any], payload: dict[str, Any] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    payload = payload or {}
    if payload.get("defect_id"):
        issue = issue_from_defect(project, payload["defect_id"], payload, today)
    else:
        found = parse_date(payload.get("found_date")) or today
        deadline = parse_date(payload.get("deadline")) or found + timedelta(days=7)
        issue = {
            "id": new_id("i"),
            "no": next_issue_no(project, today),
            "title": payload.get("title") or "质量问题",
            "defect_id": "",
            "specialty": payload.get("specialty") or "土建结构",
            "location": payload.get("location") or "",
            "severity": payload.get("severity") or "一般",
            "source": payload.get("source") or "日常巡检",
            "found_date": iso(found),
            "deadline": iso(deadline),
            "inspector": payload.get("inspector") or "",
            "owner": payload.get("owner") or "",
            "status": payload.get("status") or "待整改",
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
    project.setdefault("issues", []).insert(0, issue)
    return issue


def add_inspection(project: dict[str, Any], payload: dict[str, Any] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    payload = payload or {}
    rec = {
        "id": new_id("n"),
        "date": payload.get("date") or iso(today),
        "kind": payload.get("kind") or "日常巡检",
        "area": payload.get("area") or "",
        "inspector": payload.get("inspector") or project.get("qc_lead") or "",
        "result": payload.get("result") or "合格",
        "findings": payload.get("findings") or "",
        "follow_up": payload.get("follow_up") or "",
    }
    project.setdefault("inspections", []).insert(0, rec)
    return rec


def set_issue_status(issue: dict[str, Any], status: str, payload: dict[str, Any] | None = None, today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    payload = payload or {}
    if status not in STATUSES:
        raise ValueError("状态不合法")
    issue["status"] = status
    if status == "整改中":
        issue["rectify_plan"] = payload.get("rectify_plan") or issue.get("rectify_plan") or ""
    if status == "待复查":
        issue["rectify_desc"] = payload.get("rectify_desc") or issue.get("rectify_desc") or ""
        issue["rectify_done_date"] = payload.get("rectify_done_date") or iso(today)
    if status == "已闭合":
        issue["review_date"] = payload.get("review_date") or iso(today)
        issue["reviewer"] = payload.get("reviewer") or issue.get("reviewer") or ""
        issue["review_result"] = payload.get("review_result") or "复查合格，闭合"
        if not issue.get("rectify_done_date"):
            issue["rectify_done_date"] = iso(today)
    return issue


def demo_project(today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    project = empty_project("××小区 1# 住宅楼工程", today)
    project.update(
        {
            "location": "本市",
            "manager": "项目经理",
            "qc_lead": "质量员",
            "supervisor": "监理工程师",
            "specialty": "房屋建筑",
            "notes": "示例数据，便于先看闭环和纠偏。可删除后按现场重录。",
        }
    )
    samples = [
        {"defect_id": "honeycomb", "location": "3层①-③轴梁底", "owner": "木工班组长", "found_date": iso(today - timedelta(days=12)), "deadline": iso(today - timedelta(days=5)), "status": "待整改", "actual": "蜂窝面积约 0.3㎡", "inspector": "质量员"},
        {"defect_id": "rebar-cover", "location": "5层剪力墙暗柱", "owner": "钢筋班组长", "found_date": iso(today - timedelta(days=6)), "deadline": iso(today + timedelta(days=1)), "status": "整改中", "actual": "保护层 12mm", "allowed": "≥20mm", "deviation": "-8mm", "inspector": "质量员", "cause_method": "垫块间距过大、浇筑碰移"},
        {"defect_id": "waterproof", "location": "地下室南侧外墙", "owner": "防水班组长", "found_date": iso(today - timedelta(days=20)), "deadline": iso(today - timedelta(days=10)), "status": "待复查", "rectify_desc": "已剥离空鼓并重做卷材，待闭水", "rectify_done_date": iso(today - timedelta(days=2)), "inspector": "监理工程师"},
        {"defect_id": "masonry", "location": "2层填充墙", "owner": "砌筑班组长", "found_date": iso(today - timedelta(days=30)), "deadline": iso(today - timedelta(days=23)), "status": "已闭合", "review_date": iso(today - timedelta(days=18)), "reviewer": "质量员", "review_result": "拉结筋已补植，复查合格", "inspector": "质量员"},
        {"defect_id": "safety", "location": "7层电梯井", "owner": "安全员", "found_date": iso(today), "deadline": iso(today), "status": "待整改", "severity": "重大", "inspector": "安全员"},
    ]
    for row in reversed(samples):
        add_issue(project, row, today)
    add_inspection(
        project,
        {
            "date": iso(today),
            "kind": "日常巡检",
            "area": "主体 3～7 层",
            "inspector": "质量员",
            "result": "有隐患",
            "findings": "3层梁底蜂窝；7层电梯井防护未恢复。",
            "follow_up": "已下发整改，纳入问题台账。",
        },
        today,
    )
    add_inspection(
        project,
        {
            "date": iso(today - timedelta(days=6)),
            "kind": "旁站",
            "area": "5层剪力墙浇筑",
            "inspector": "监理工程师",
            "result": "合格（有一般问题）",
            "findings": "保护层垫块局部偏少，已要求补设。",
            "follow_up": "列入台账跟踪。",
        },
        today,
    )
    return project
