from __future__ import annotations

from typing import Any


def check_floor(room, tile: dict, layout: dict) -> list[dict[str, Any]]:
    tw, th = tile["w"], tile["h"]
    min_ok = min(tw, th) / 3
    rec = min(tw, th) / 2
    checks = [
        {
            "ok": layout["min_edge"] + 1e-6 >= min_ok,
            "code": "GB 50210 / 工艺",
            "msg": f"边砖最小 {layout['min_edge']*1000:.0f}mm，不宜小于整砖 1/3（{min_ok*1000:.0f}mm）",
        },
        {
            "ok": layout["min_edge"] + 1e-6 >= rec,
            "code": "工艺建议",
            "msg": f"边砖 {layout['min_edge']*1000:.0f}mm，宜不小于 1/2 整砖（{rec*1000:.0f}mm）；不满足时把非整砖放到阴角或衣柜下",
        },
        {
            "ok": 0.001 <= tile["grout"] <= 0.005,
            "code": "GB 50210",
            "msg": f"砖缝 {tile['grout']*1000:.1f}mm（抛光砖宜 1～2mm，仿古 3～5mm）",
        },
        {
            "ok": True,
            "code": "GB 50327",
            "msg": "门口、走道宜整砖或对缝；本排版已自动寻找较大边砖",
        },
    ]
    if room.kind == "卫生间":
        checks.append({"ok": True, "code": "GB 50210", "msg": "卫生间地面应坡向地漏，坡度 1%～2%，本图为平面排砖示意，找坡在现场"})
    return checks


def check_wall(room, tile, walls: list[dict]) -> list[dict[str, Any]]:
    min_edge = min((w["min_edge"] for w in walls), default=0)
    min_ok = min(tile["w"], tile["h"]) / 3
    return [
        {"ok": min_edge >= min_ok - 1e-6, "code": "工艺", "msg": f"墙砖边条最小 {min_edge*1000:.0f}mm，不宜小于整砖 1/3"},
        {"ok": True, "code": "GB 50210", "msg": "阳角宜整砖或45°碰角；非整砖放阴角。门窗洞口四周应套割、交圈"},
        {"ok": room.height >= 2.2, "code": "GB 50096", "msg": f"室内净高 {room.height}m（住宅卧室/起居不宜小于 2.4m，厨房卫生间 2.2m）"},
    ]


def check_ceiling(room, ceil: dict) -> list[dict[str, Any]]:
    sp = ceil["spec"]
    return [
        {"ok": ceil["main_spacing"] <= 1.001, "code": "石膏板吊顶工艺", "msg": f"主龙骨间距 {ceil['main_spacing']}m（不宜大于 1.0m）"},
        {"ok": ceil["secondary_spacing"] <= 0.401 + 1e-6 or ceil["kind"] != "石膏板", "code": "工艺", "msg": f"次龙骨间距 {ceil['secondary_spacing']}m（石膏板次龙骨宜 300～400mm）"},
        {"ok": True, "code": "工艺", "msg": f"吊杆距墙按 {sp['edge']}m 起排，间距约 {sp['hanger']}m；检修口 {int(ceil['hatch']['w']*1000)}×{int(ceil['hatch']['h']*1000)} 放角落"},
        {"ok": True, "code": "GB 50210", "msg": "灯具、喷淋处应加附骨；潮湿房间用防水板。石膏板应错缝"},
    ]


def quantities(task: str, room, payload: dict, tile=None, ceil=None) -> list[dict[str, Any]]:
    rows = [{"name": "房间面积", "qty": round(room.area, 2), "unit": "㎡"}]
    if task == "floor" and tile:
        n = payload["count"]
        waste = tile.get("waste", 0.05)
        if payload["pattern"] == "diagonal":
            waste = max(waste, 0.12)
        buy = n * (1 + waste)
        rows += [
            {"name": f"地砖 {int(tile['w']*1000)}×{int(tile['h']*1000)} 块数", "qty": n, "unit": "块"},
            {"name": "其中切割", "qty": payload["cuts"], "unit": "块"},
            {"name": f"采购（含损耗 {waste*100:.0f}%）", "qty": round(buy, 1), "unit": "块"},
            {"name": "铺贴面积", "qty": round(payload["area"], 2), "unit": "㎡"},
        ]
    if task == "wall" and tile:
        n = sum(w["count"] for w in payload)
        cuts = sum(w["cuts"] for w in payload)
        waste = tile.get("waste", 0.08)
        rows += [
            {"name": "墙砖块数", "qty": n, "unit": "块"},
            {"name": "其中切割", "qty": cuts, "unit": "块"},
            {"name": f"采购（含损耗 {waste*100:.0f}%）", "qty": round(n * (1 + waste), 1), "unit": "块"},
            {"name": "墙面面积（扣门窗）", "qty": round(room.wall_area, 2), "unit": "㎡"},
        ]
    if task == "ceiling" and ceil:
        rows += [
            {"name": "吊顶板", "qty": payload["panel_count"], "unit": "块"},
            {"name": "主龙骨", "qty": len(payload["mains"]), "unit": "根"},
            {"name": "次龙骨", "qty": len(payload["seconds"]), "unit": "根"},
            {"name": "吊杆", "qty": payload["hanger_count"], "unit": "套"},
            {"name": "灯位", "qty": len(payload["lights"]), "unit": "个"},
            {"name": "检修口", "qty": 1, "unit": "个"},
        ]
    if task == "furniture":
        rows += [{"name": it["name"], "qty": 1, "unit": "件"} for it in payload["items"]]
    return rows
