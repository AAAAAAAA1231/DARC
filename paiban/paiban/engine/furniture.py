from __future__ import annotations

from typing import Any


def layout_furniture(room_w: float, room_d: float, kind: str, catalog: dict[str, Any]) -> dict[str, Any]:
    items_spec = catalog.get("furniture", {}).get(kind) or catalog["furniture"]["客厅"]
    placed = []
    if kind == "卧室":
        placed.append(_item("1.8m床", 0.1, (room_d - 2.0) / 2, 1.8, 2.0, 0.6))
        placed.append(_item("床头柜", 0.1, (room_d - 2.0) / 2 - 0.5, 0.5, 0.4, 0.0))
        placed.append(_item("床头柜", 0.1, (room_d - 2.0) / 2 + 2.0, 0.5, 0.4, 0.0))
        placed.append(_item("衣柜", room_w - 0.65, 0.15, 0.6, min(2.4, room_d - 0.3), 0.7))
        if room_w > 3.4:
            placed.append(_item("书桌", room_w - 0.7, room_d - 1.4, 0.6, 1.2, 0.8))
    elif kind == "卫生间":
        placed.append(_item("马桶", 0.15, 0.15, 0.4, 0.7, 0.3))
        placed.append(_item("淋浴区", room_w - 1.05, room_d - 1.05, 0.9, 0.9, 0.6))
        placed.append(_item("台盆柜", room_w - 0.95, 0.1, 0.8, 0.5, 0.6))
    elif kind == "厨房":
        placed.append(_item("操作台", 0.0, 0.0, room_w, 0.6, 0.9))
        placed.append(_item("冰箱位", 0.0, 0.6, 0.7, 0.7, 0.6))
    elif kind == "餐厅":
        placed.append(_item("餐桌", (room_w - 1.4) / 2, (room_d - 0.85) / 2, 1.4, 0.85, 0.8))
        for i, (dx, dy) in enumerate(((-0.55, 0.2), (1.5, 0.2), (0.45, -0.55), (0.45, 0.95))):
            placed.append(_item(f"餐椅{i+1}", (room_w - 1.4) / 2 + dx, (room_d - 0.85) / 2 + dy, 0.45, 0.5, 0.8))
    else:  # 客厅
        placed.append(_item("三人沙发", (room_w - 2.2) / 2, 0.1, 2.2, 0.9, 0.8))
        placed.append(_item("茶几", (room_w - 1.2) / 2, 1.35, 1.2, 0.6, 0.35))
        placed.append(_item("电视柜", (room_w - 1.8) / 2, room_d - 0.5, 1.8, 0.4, 0.8))
        if room_w > 4.2:
            placed.append(_item("单人沙发", 0.15, 1.4, 0.85, 0.85, 0.6))

    checks = []
    for p in placed:
        if p["x"] < -0.01 or p["y"] < -0.01 or p["x"] + p["w"] > room_w + 0.02 or p["y"] + p["d"] > room_d + 0.02:
            checks.append({"ok": False, "item": p["name"], "msg": f"{p['name']} 超出房间，需改尺寸或换墙"})
        else:
            checks.append({"ok": True, "item": p["name"], "msg": f"{p['name']} 在房间内"})
    # sofa-table clearance
    names = {p["name"]: p for p in placed}
    if "三人沙发" in names and "茶几" in names:
        gap = names["茶几"]["y"] - (names["三人沙发"]["y"] + names["三人沙发"]["d"])
        checks.append({"ok": 0.3 <= gap <= 0.5, "item": "茶几间距", "msg": f"沙发-茶几净距 {gap:.2f}m（宜 0.30～0.40m）"})
    if "1.8m床" in names:
        bed = names["1.8m床"]
        side = bed["y"]
        checks.append({"ok": side >= 0.5 or room_d - (bed["y"] + bed["d"]) >= 0.5, "item": "床边通道", "msg": "床侧通道不宜小于 0.5～0.6m"})
    aisle = _max_aisle(room_w, room_d, placed)
    checks.append({"ok": aisle >= 0.8, "item": "主要通道", "msg": f"估算主要通道 {aisle:.2f}m（不宜小于 0.8m）"})
    return {"items": placed, "checks": checks, "kind": kind, "catalog": items_spec}


def _item(name, x, y, w, d, clear):
    return {"name": name, "x": round(x, 3), "y": round(y, 3), "w": w, "d": d, "clear": clear}


def _max_aisle(W, D, items) -> float:
    # crude: empty band along center
    cy = D / 2
    blocked = [it for it in items if it["y"] <= cy <= it["y"] + it["d"]]
    if not blocked:
        return min(W, D)
    xs = sorted([(it["x"], it["x"] + it["w"]) for it in blocked])
    gaps = [xs[0][0], W - xs[-1][1]]
    for a, b in zip(xs, xs[1:]):
        gaps.append(b[0] - a[1])
    return max(0.0, max(gaps))
