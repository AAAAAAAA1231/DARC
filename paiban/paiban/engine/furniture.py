from __future__ import annotations

from typing import Any


def layout_furniture(
    room_w: float,
    room_d: float,
    kind: str,
    catalog: dict[str, Any],
    height: float = 2.8,
    project_type: str = "既有",
    room_name: str = "",
) -> dict[str, Any]:
    """Arrange typical furniture and leave clearances required by GB 55038-2025 / GB 50096-2011."""
    placed: list[dict[str, Any]] = []
    new_build = project_type == "新建"
    door_w = {"客厅": 0.90 if new_build else 0.80, "卧室": 0.80, "厨房": 0.70, "卫生间": 0.70, "餐厅": 0.90 if new_build else 0.80, "走廊": 0.90 if new_build else 0.80}.get(kind, 0.80)

    if kind == "卧室":
        bed_w, bed_d = 1.80, 2.00
        if room_w < bed_w + 0.60:
            bed_w = 1.50
        aisle = 0.60
        placed.append(_item("双人床", 0.05, (room_d - bed_d) / 2, bed_w, bed_d, aisle))
        by = (room_d - bed_d) / 2
        placed.append(_item("床头柜", 0.05, max(0.05, by - 0.45), 0.45, 0.40, 0.0))
        placed.append(_item("床头柜", 0.05, min(room_d - 0.45, by + bed_d + 0.05), 0.45, 0.40, 0.0))
        ward_d = min(0.60, room_w * 0.2)
        placed.append(_item("衣柜", room_w - ward_d - 0.02, 0.10, ward_d, min(2.0, room_d - 0.2), 0.70))
    elif kind == "卫生间":
        placed.append(_item("便器", 0.10, 0.10, 0.40, 0.70, 0.50))
        placed.append(_item("洗面器", room_w - 0.65, 0.10, 0.55, 0.45, 0.60))
        sh = 0.90
        placed.append(_item("淋浴区", room_w - sh - 0.05, room_d - sh - 0.05, sh, sh, 0.60))
        placed.append(_item("洗衣机位", 0.10, room_d - 0.70, 0.60, 0.60, 0.40))
    elif kind == "厨房":
        counter = 0.60
        placed.append(_item("操作台", 0.0, 0.0, room_w, counter, 0.90))
        placed.append(_item("洗涤池", 0.15, 0.0, 0.50, counter, 0.90))
        placed.append(_item("灶具", room_w - 0.85, 0.0, 0.70, counter, 0.90))
        placed.append(_item("排油烟机", room_w - 0.85, 0.0, 0.70, 0.15, 0.0))
        if room_d - counter >= 1.50:
            placed.append(_item("冰箱位", 0.05, counter + 0.90, 0.70, 0.65, 0.60))
    elif kind == "餐厅":
        tw, td = min(1.40, max(0.7, room_w - 1.70)), min(0.85, max(0.5, room_d - 1.70))
        placed.append(_item("餐桌", (room_w - tw) / 2, (room_d - td) / 2, tw, td, 0.80))
    elif kind == "走廊":
        placed.append(_item("通行净宽示意", 0.0, 0.0, room_w, room_d, 0.0))
    else:
        sofa_w = min(2.20, room_w - 0.40)
        placed.append(_item("三人沙发", (room_w - sofa_w) / 2, 0.10, sofa_w, 0.90, 0.80))
        placed.append(_item("茶几", (room_w - 1.20) / 2, 1.35, 1.20, 0.60, 0.35))
        placed.append(_item("电视柜", (room_w - min(1.80, room_w - 0.4)) / 2, room_d - 0.45, min(1.80, room_w - 0.4), 0.40, 0.80))

    checks = _gb_space_checks(kind, room_w, room_d, height, door_w, project_type, room_name)
    for p in placed:
        if p["name"] == "通行净宽示意":
            continue
        if p["x"] < -0.02 or p["y"] < -0.02 or p["x"] + p["w"] > room_w + 0.03 or p["y"] + p["d"] > room_d + 0.03:
            checks.append({"ok": False, "hard": True, "kind": "code", "code": "布置", "item": p["name"], "msg": f"{p['name']} 超出房间轮廓"})
    if kind == "客厅" and any(i["name"] == "三人沙发" for i in placed) and any(i["name"] == "茶几" for i in placed):
        sofa = next(i for i in placed if i["name"] == "三人沙发")
        tea = next(i for i in placed if i["name"] == "茶几")
        gap = tea["y"] - (sofa["y"] + sofa["d"])
        checks.append({"ok": 0.30 <= gap <= 0.45, "hard": False, "kind": "craft", "code": "人体工学", "item": "茶几间距", "msg": f"沙发—茶几净距 {gap:.2f}m（宜 0.30～0.40m，非国标限值）"})
    if kind == "卧室" and any("床" in i["name"] for i in placed):
        bed = next(i for i in placed if "床" in i["name"])
        side = max(bed["y"], room_d - (bed["y"] + bed["d"]))
        checks.append({"ok": side >= 0.50, "hard": False, "kind": "craft", "code": "通行", "item": "床边通道", "msg": f"床侧通道 {side:.2f}m（不宜小于 0.50m，非国标限值）"})
    if kind == "卫生间":
        toilet = next((i for i in placed if i["name"] == "便器"), None)
        if toilet:
            front = room_d - (toilet["y"] + toilet["d"])
            checks.append({"ok": front >= 0.50 or room_w - (toilet["x"] + toilet["w"]) >= 0.50, "hard": False, "kind": "craft", "code": "使用净距", "item": "便器前方", "msg": f"便器前方净距约 {front:.2f}m（不宜小于 0.50m）"})
        names = {i["name"] for i in placed}
        checks.append({"ok": {"便器", "洗面器", "淋浴区"} <= names, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.6", "item": "卫生器具", "msg": "集中配置卫生间应有便器、洗浴器、洗面器（或预留）；便器卫生间的门不应直接开向厨房"})
        checks.append({"ok": "洗衣机位" in names, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.11", "item": "洗衣机", "msg": "每套住宅应设洗衣机位置及给排水条件；本图在卫生间预留洗衣机位（也可设于阳台/厨房）"})
    if kind == "厨房":
        counter = next((i for i in placed if i["name"] == "操作台"), None)
        if counter:
            aisle = room_d - counter["d"]
            checks.append({"ok": aisle >= 0.90 - 1e-6, "hard": True, "kind": "code", "code": "GB 50096-2011 5.4.3", "item": "操作台前", "msg": f"单排厨房操作台前净宽 {aisle:.2f}m（不应小于 0.90m）"})
        have = {i["name"] for i in placed}
        checks.append({"ok": "洗涤池" in have and "灶具" in have and "排油烟机" in have, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.5", "item": "厨房设施", "msg": "应配置洗涤池、水龙头、案台、灶具、排油烟机等或预留位置"})

    aisle = _max_aisle(room_w, room_d, [p for p in placed if p["name"] != "通行净宽示意"])
    if kind == "走廊":
        aisle = min(room_w, room_d)
        name = room_name or ""
        if any(k in name for k in ("入口", "玄关", "户门")):
            need, label = 1.10, "套内入口过道"
        elif any(k in name for k in ("厨", "卫", "贮藏", "储藏")):
            need, label = 0.90, "通往厨房/卫生间/贮藏室的过道"
        else:
            need, label = 1.00, "通往卧室/起居室的过道"
        checks.append({"ok": aisle + 1e-6 >= need, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.13", "item": "过道净宽", "msg": f"{label}短边 {aisle:.2f}m（不应小于 {need:.2f}m）"})
    else:
        need = {"客厅": 1.00, "卧室": 1.00, "厨房": 0.90, "卫生间": 0.90, "餐厅": 1.00}.get(kind, 0.90)
        checks.append({"ok": aisle + 1e-6 >= need, "hard": False, "kind": "craft", "code": "GB 55038-2025 4.1.13", "item": "主要通道", "msg": f"估算家具间通道 {aisle:.2f}m（套内过道：入口 1.10 / 卧起 1.00 / 厨卫 0.90；本项为布置校核）"})

    return {"items": placed, "checks": checks, "kind": kind, "door_clear": door_w, "catalog": catalog.get("furniture", {}).get(kind) or []}


def _gb_space_checks(kind: str, w: float, d: float, h: float, door_w: float, project_type: str, room_name: str) -> list[dict[str, Any]]:
    area = w * d
    short = min(w, d)
    new_build = project_type == "新建"
    checks: list[dict[str, Any]] = []
    if new_build:
        checks.append({"ok": h >= 3.00 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.2-1", "item": "层高", "msg": f"新建住宅层高不应低于 3.00m；当前 {h:.2f}m"})
    else:
        checks.append({"ok": True, "hard": False, "kind": "note", "code": "GB 55038-2025 4.1.2-1", "item": "层高", "msg": f"新建住宅层高不应低于 3.00m。既有装修当执行确有困难时不应低于原建造标准；当前层高 {h:.2f}m"})
    if kind == "卧室":
        checks.append({"ok": area >= 5.0 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.1", "item": "卧室面积", "msg": f"卧室使用面积 {area:.2f}㎡（不应小于 5㎡；兼起居的卧室不应小于 9㎡）"})
        checks.append({"ok": short >= 1.80 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.1", "item": "卧室短边", "msg": f"短边净宽 {short:.2f}m（不应小于 1.80m）"})
        checks.append({"ok": h >= 2.60 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.2-2", "item": "净高", "msg": f"室内净高按层高 {h:.2f}m 计（卧室不应低于 2.60m）"})
        checks.append({"ok": door_w >= 0.80 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.14", "item": "卧室门", "msg": f"卧室门通行净宽按 {door_w:.2f}m 计（不应小于 0.80m，指装修完成后的通行净宽）"})
    elif kind == "客厅":
        checks.append({"ok": h >= 2.60 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.2-2", "item": "净高", "msg": f"室内净高按层高 {h:.2f}m 计（起居室不应低于 2.60m）"})
        need_door = 0.90 if new_build else 0.80
        label = "新建户门不应小于 0.90m" if new_build else "既有住宅改造户门不应小于 0.80m"
        checks.append({"ok": door_w + 1e-6 >= need_door, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.14", "item": "户门", "msg": f"户门通行净宽按 {door_w:.2f}m 计（{label}；本图将客厅门按户门校核）"})
    elif kind == "厨房":
        checks.append({"ok": area >= 3.5 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.4", "item": "厨房面积", "msg": f"厨房使用面积 {area:.2f}㎡（不应小于 3.5㎡）"})
        checks.append({"ok": h >= 2.20 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.2-4", "item": "净高", "msg": f"室内净高按层高 {h:.2f}m 计（厨房不应低于 2.20m）"})
        checks.append({"ok": door_w >= 0.70 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.14", "item": "厨房门", "msg": f"厨房门通行净宽按 {door_w:.2f}m 计（不应小于 0.70m）"})
    elif kind == "卫生间":
        three = True
        checks.append({"ok": area >= 2.5 - 1e-6 or not three, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.6", "item": "卫生间面积", "msg": f"三件套卫生间使用面积 {area:.2f}㎡（便器、洗浴器、洗面器集中配置时不应小于 2.5㎡）"})
        checks.append({"ok": h >= 2.20 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.2-4", "item": "净高", "msg": f"室内净高按层高 {h:.2f}m 计（卫生间不应低于 2.20m）"})
        checks.append({"ok": door_w >= 0.70 - 1e-6, "hard": True, "kind": "code", "code": "GB 55038-2025 4.1.14", "item": "卫生间门", "msg": f"卫生间门通行净宽按 {door_w:.2f}m 计（不应小于 0.70m）"})
    return checks


def _item(name, x, y, w, d, clear):
    return {"name": name, "x": round(x, 3), "y": round(y, 3), "w": round(w, 3), "d": round(d, 3), "clear": clear}


def _max_aisle(W, D, items) -> float:
    if not items:
        return min(W, D)
    cy = D / 2
    blocked = [it for it in items if it["y"] <= cy <= it["y"] + it["d"]]
    if not blocked:
        return min(W, D)
    xs = sorted([(it["x"], it["x"] + it["w"]) for it in blocked])
    gaps = [xs[0][0], W - xs[-1][1]]
    for a, b in zip(xs, xs[1:]):
        gaps.append(b[0] - a[1])
    return max(0.0, max(gaps))
