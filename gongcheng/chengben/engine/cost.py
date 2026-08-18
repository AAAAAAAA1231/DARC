from __future__ import annotations

import copy
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Any

from chengben.config import RESOURCES

CORR_STATUSES = ("待落实", "落实中", "已验证", "已闭合")
OPEN_CORR = {"待落实", "落实中", "已验证"}


def parse_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()[:10]
    return date.fromisoformat(text) if text else None


def iso(value: date | None) -> str:
    return value.isoformat() if value else ""


def money(value: Any) -> float:
    try:
        return round(float(value or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def qty(value: Any) -> float:
    try:
        return round(float(value or 0), 4)
    except (TypeError, ValueError):
        return 0.0


def new_id(prefix: str = "c") -> str:
    return prefix + uuid.uuid4().hex[:8]


def load_catalog() -> dict[str, Any]:
    return json.loads((RESOURCES / "catalog.json").read_text(encoding="utf-8"))


def get_template(template_id: str) -> dict[str, Any]:
    for item in load_catalog()["templates"]:
        if item["id"] == template_id:
            return item
    raise KeyError(f"未找到成本模板：{template_id}")


def budget_of(row: dict[str, Any]) -> float:
    amount = money(row.get("budget_amount"))
    if amount:
        return amount
    return round(qty(row.get("budget_qty")) * money(row.get("budget_price")), 2)


def item_calc(item: dict[str, Any]) -> dict[str, Any]:
    budget = budget_of(item)
    change = money(item.get("change_amount"))
    actual = money(item.get("actual_amount"))
    remain = money(item.get("remain_amount"))
    target = round(budget + change, 2)
    forecast = round(actual + remain, 2)
    deviation = round(forecast - target, 2)
    rate = round(deviation / target, 4) if target else 0.0
    if target and deviation >= target * 0.10:
        flag = "超支"
    elif target and deviation >= target * 0.05:
        flag = "预警"
    elif target and deviation <= -target * 0.02:
        flag = "节约"
    else:
        flag = "正常"
    bq = qty(item.get("budget_qty"))
    aq = qty(item.get("actual_qty"))
    bp = money(item.get("budget_price"))
    qty_diff = round(aq - bq, 4) if bq or aq else 0.0
    actual_price = round(actual / aq, 2) if aq else 0.0
    price_diff = round(actual_price - bp, 2) if bp and aq else 0.0
    return {
        "budget_amount": budget,
        "change_amount": change,
        "actual_amount": actual,
        "remain_amount": remain,
        "target": target,
        "forecast": forecast,
        "deviation": deviation,
        "deviation_rate": rate,
        "flag": flag,
        "qty_diff": qty_diff,
        "actual_price": actual_price,
        "price_diff": price_diff,
    }


def enrich_project(project: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    data = copy.deepcopy(project)
    today = today or date.today()
    items = data.get("items") or []
    by_cat: dict[str, dict[str, float]] = {}
    totals = {"budget": 0.0, "change": 0.0, "target": 0.0, "actual": 0.0, "remain": 0.0, "forecast": 0.0, "deviation": 0.0}
    warn = over = save = 0
    for item in items:
        calc = item_calc(item)
        item.update(calc)
        totals["budget"] += calc["budget_amount"]
        totals["change"] += calc["change_amount"]
        totals["target"] += calc["target"]
        totals["actual"] += calc["actual_amount"]
        totals["remain"] += calc["remain_amount"]
        totals["forecast"] += calc["forecast"]
        totals["deviation"] += calc["deviation"]
        cat = item.get("category") or "其他"
        bucket = by_cat.setdefault(cat, {"target": 0.0, "actual": 0.0, "forecast": 0.0, "deviation": 0.0})
        bucket["target"] += calc["target"]
        bucket["actual"] += calc["actual_amount"]
        bucket["forecast"] += calc["forecast"]
        bucket["deviation"] += calc["deviation"]
        if calc["flag"] == "超支":
            over += 1
        elif calc["flag"] == "预警":
            warn += 1
        elif calc["flag"] == "节约":
            save += 1
    for k, v in list(totals.items()):
        totals[k] = round(v, 2)
    for bucket in by_cat.values():
        for k, v in list(bucket.items()):
            bucket[k] = round(v, 2)
    rate = round(totals["deviation"] / totals["target"], 4) if totals["target"] else 0.0
    corrs = data.get("corrections") or []
    open_corr = 0
    overdue_corr = 0
    for corr in corrs:
        status = corr.get("status") or "待落实"
        closed = status == "已闭合"
        deadline = parse_date(corr.get("deadline"))
        overdue = bool(not closed and deadline and deadline < today)
        corr["closed"] = closed
        corr["overdue"] = overdue
        if not closed:
            open_corr += 1
        if overdue:
            overdue_corr += 1
    data["stats"] = {
        "today": iso(today),
        "item_count": len(items),
        "log_count": len(data.get("logs") or []),
        "change_count": len(data.get("changes") or []),
        "open_corr": open_corr,
        "overdue_corr": overdue_corr,
        "warn_count": warn,
        "over_count": over,
        "save_count": save,
        "deviation_rate": rate,
        "by_category": by_cat,
        **totals,
    }
    return data


def empty_project(name: str = "新建工程") -> dict[str, Any]:
    return {
        "id": new_id("p"),
        "name": name,
        "location": "",
        "manager": "",
        "cost_lead": "",
        "specialty": "",
        "contract_amount": 0,
        "notes": "",
        "items": [],
        "logs": [],
        "corrections": [],
        "changes": [],
    }


def _next_no(rows: list[dict[str, Any]], prefix: str, year: int) -> str:
    head = f"{prefix}-{year}-"
    nums = []
    for row in rows:
        no = str(row.get("no") or "")
        if no.startswith(head) and no[len(head):].isdigit():
            nums.append(int(no[len(head):]))
    return f"{head}{(max(nums) if nums else 0) + 1:03d}"


def instantiate_template(template_id: str, *, name: str = "", location: str = "", manager: str = "", cost_lead: str = "") -> dict[str, Any]:
    tmpl = get_template(template_id)
    items = []
    for row in tmpl["items"]:
        bq = qty(row.get("budget_qty"))
        bp = money(row.get("budget_price"))
        budget = budget_of(row)
        items.append(
            {
                "id": new_id("i"),
                "code": row["code"],
                "name": row["name"],
                "category": row["category"],
                "unit": row.get("unit") or "项",
                "budget_qty": bq,
                "budget_price": bp,
                "budget_amount": budget,
                "change_amount": 0.0,
                "actual_qty": 0.0,
                "actual_amount": 0.0,
                "remain_amount": budget,
                "owner": "",
                "notes": "",
            }
        )
    project = empty_project(name or tmpl["name"])
    project.update(
        {
            "location": location,
            "manager": manager,
            "cost_lead": cost_lead,
            "specialty": tmpl.get("specialty") or "",
            "template_id": template_id,
            "notes": tmpl.get("notes") or "",
            "items": items,
            "contract_amount": round(sum(budget_of(r) for r in tmpl["items"]) * 1.08, 2),
        }
    )
    return project


def apply_demo_progress(project: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    """Fill a mid-project actual/remain mix so the board is not all zeros."""
    today = today or date.today()
    data = copy.deepcopy(project)
    ratios = [0.92, 0.88, 1.06, 0.97, 0.70, 0.55, 0.80, 0.75, 0.40, 0.48, 0.35, 0.60, 0.85, 0.50]
    for i, item in enumerate(data.get("items") or []):
        ratio = ratios[i % len(ratios)]
        target = budget_of(item)
        actual = round(target * min(ratio, 1.15) * 0.55, 2)
        remain = round(max(target * 0.45, target * ratio - actual), 2)
        item["actual_amount"] = actual
        item["remain_amount"] = remain
        if qty(item.get("budget_qty")):
            item["actual_qty"] = round(qty(item["budget_qty"]) * 0.55, 4)
    items = data["items"]
    if items:
        hot = items[2] if len(items) > 2 else items[0]
        hot["remain_amount"] = round(money(hot["remain_amount"]) + money(hot["budget_amount"]) * 0.12, 2)
        data["corrections"] = [
            {
                "id": new_id("j"),
                "no": f"JB-{today.year}-001",
                "item_id": hot["id"],
                "date": iso(today - timedelta(days=8)),
                "title": f"{hot['name']}预计超支纠偏",
                "kind": "价差" if money(hot.get("budget_price")) else "量差",
                "deviation_amount": round(money(hot["budget_amount"]) * 0.12, 2),
                "cause": "材料单价上涨，现场损耗略超目标。",
                "action": "锁定剩余采购价；班组交底降低损耗；能调规的部位办理签证。",
                "owner": data.get("cost_lead") or "成本员",
                "deadline": iso(today + timedelta(days=7)),
                "status": "落实中",
                "notes": "",
            }
        ]
        data["changes"] = [
            {
                "id": new_id("z"),
                "no": f"QZ-{today.year}-001",
                "date": iso(today - timedelta(days=20)),
                "title": "地下室增加止水钢板",
                "amount": 86000,
                "item_id": items[5]["id"] if len(items) > 5 else items[0]["id"],
                "approved": True,
                "notes": "设计变更已批准，纳入动态成本。",
            }
        ]
        change = data["changes"][0]
        for item in items:
            if item["id"] == change["item_id"]:
                item["change_amount"] = money(change["amount"])
                break
        data["logs"] = [
            {
                "id": new_id("l"),
                "date": iso(today - timedelta(days=3)),
                "item_id": items[2]["id"] if len(items) > 2 else items[0]["id"],
                "kind": "材料进场",
                "qty": 40,
                "amount": 168000,
                "voucher": "CGRK-018",
                "notes": "钢筋进场验收合格。",
            }
        ]
    return data


def add_item(project: dict[str, Any], payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = payload or {}
    bq = qty(payload.get("budget_qty"))
    bp = money(payload.get("budget_price"))
    budget = money(payload.get("budget_amount")) or round(bq * bp, 2)
    item = {
        "id": new_id("i"),
        "code": payload.get("code") or _next_code(project),
        "name": payload.get("name") or "新科目",
        "category": payload.get("category") or "材料费",
        "unit": payload.get("unit") or "项",
        "budget_qty": bq,
        "budget_price": bp,
        "budget_amount": budget,
        "change_amount": money(payload.get("change_amount")),
        "actual_qty": qty(payload.get("actual_qty")),
        "actual_amount": money(payload.get("actual_amount")),
        "remain_amount": money(payload.get("remain_amount")) if payload.get("remain_amount") not in (None, "") else budget,
        "owner": payload.get("owner") or "",
        "notes": payload.get("notes") or "",
    }
    project.setdefault("items", []).append(item)
    return item


def _next_code(project: dict[str, Any]) -> str:
    n = 1 + len(project.get("items") or [])
    return f"9.{n:02d}"


def add_log(project: dict[str, Any], payload: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    rec = {
        "id": new_id("l"),
        "date": payload.get("date") or iso(today),
        "item_id": payload.get("item_id") or "",
        "kind": payload.get("kind") or "其他",
        "qty": qty(payload.get("qty")),
        "amount": money(payload.get("amount")),
        "voucher": payload.get("voucher") or "",
        "notes": payload.get("notes") or "",
    }
    project.setdefault("logs", []).insert(0, rec)
    item = next((x for x in project.get("items") or [] if x["id"] == rec["item_id"]), None)
    if item and rec["amount"]:
        item["actual_amount"] = round(money(item.get("actual_amount")) + rec["amount"], 2)
        item["actual_qty"] = round(qty(item.get("actual_qty")) + rec["qty"], 4)
        item["remain_amount"] = max(0.0, round(money(item.get("remain_amount")) - rec["amount"], 2))
    return rec


def add_change(project: dict[str, Any], payload: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    rec = {
        "id": new_id("z"),
        "no": payload.get("no") or _next_no(project.get("changes") or [], "QZ", today.year),
        "date": payload.get("date") or iso(today),
        "title": payload.get("title") or "签证变更",
        "amount": money(payload.get("amount")),
        "item_id": payload.get("item_id") or "",
        "approved": bool(payload.get("approved", True)),
        "notes": payload.get("notes") or "",
    }
    project.setdefault("changes", []).insert(0, rec)
    if rec["approved"] and rec["item_id"] and rec["amount"]:
        item = next((x for x in project.get("items") or [] if x["id"] == rec["item_id"]), None)
        if item:
            item["change_amount"] = round(money(item.get("change_amount")) + rec["amount"], 2)
            item["remain_amount"] = round(money(item.get("remain_amount")) + rec["amount"], 2)
    return rec


def add_correction(project: dict[str, Any], payload: dict[str, Any], today: date | None = None) -> dict[str, Any]:
    today = today or date.today()
    rec = {
        "id": new_id("j"),
        "no": payload.get("no") or _next_no(project.get("corrections") or [], "JB", today.year),
        "item_id": payload.get("item_id") or "",
        "date": payload.get("date") or iso(today),
        "title": payload.get("title") or "成本纠偏",
        "kind": payload.get("kind") or "其他",
        "deviation_amount": money(payload.get("deviation_amount")),
        "cause": payload.get("cause") or "",
        "action": payload.get("action") or "",
        "owner": payload.get("owner") or "",
        "deadline": payload.get("deadline") or iso(today + timedelta(days=7)),
        "status": payload.get("status") or "待落实",
        "notes": payload.get("notes") or "",
    }
    project.setdefault("corrections", []).insert(0, rec)
    return rec


def set_corr_status(corr: dict[str, Any], status: str) -> dict[str, Any]:
    if status not in CORR_STATUSES:
        raise ValueError("纠偏状态不合法")
    corr["status"] = status
    return corr
