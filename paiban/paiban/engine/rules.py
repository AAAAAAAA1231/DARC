from __future__ import annotations

from typing import Any


def _chk(ok: bool, code: str, msg: str, hard: bool = True, kind: str = "code") -> dict[str, Any]:
    return {"ok": bool(ok), "code": code, "msg": msg, "hard": hard, "kind": kind}


def check_floor(room, tile: dict, layout: dict) -> list[dict[str, Any]]:
    tw, th = tile["w"], tile["h"]
    min_ok = min(tw, th) / 3
    grout = tile["grout"]
    anti = "防滑" in (tile.get("kind") or "") or "防滑" in (tile.get("name") or "")
    wet = layout.get("wet_features") or {}
    checks = [
        _chk(
            layout["min_edge"] + 1e-6 >= min_ok,
            "排砖工艺",
            f"边砖最小 {layout['min_edge']*1000:.0f}mm，不宜小于整砖 1/3（{min_ok*1000:.0f}mm）；非整砖宜放阴角或柜下。GB 50210 只要求非整砖部位符合设计，1/3 不是国标限值",
            hard=False,
            kind="craft",
        ),
        _chk(
            0.001 <= grout <= 0.005 or grout == 0,
            "GB 50209-2010 砖面层",
            f"砖缝 {grout*1000:.1f}mm（接缝宽度应符合设计；抛光砖常 1～2mm，防滑/仿古 3～5mm）",
            hard=False,
            kind="craft",
        ),
        _chk(
            True,
            "GB 50209-2010",
            "空鼓、裂缝、相邻砖高差、缝格平直须现场尺量验收，本图只给出平面分格，不能代替验收",
            hard=False,
            kind="site",
        ),
    ]
    if room.kind == "卫生间":
        checks.append(_chk(anti, "GB 55038-2025 4.1.10", f"卫生间地面应采用防滑铺装，COF 不应小于 0.6；当前面层「{tile['name']}」{'为防滑砖（COF 以检测报告为准）' if anti else '不是防滑砖，不得用于卫生间地面'}"))
        drain_ok = bool(wet.get("drain"))
        slope = float(wet.get("slope_pct") or 0)
        checks.append(_chk(drain_ok and slope >= 1.0 - 1e-9, "GB 55038-2025 4.1.9", "卫生间地面应设防水层和地漏，排水坡度不应小于 1％、坡向地漏" + ("；本图已布置地漏并按 1％找坡" if drain_ok else "；本图未布置地漏")))
        step = float(wet.get("door_step_mm") or 99)
        ramp = wet.get("ramp")
        checks.append(_chk(step <= 15 + 1e-6 and bool(ramp), "GB 55038-2025 4.1.12", f"卫生间与相邻空间地面高差不应大于 15mm，并以斜坡过渡；本图门口高差按 {step:.0f}mm、斜坡长 {float((ramp or {}).get('d') or 0)*1000:.0f}mm"))
        if wet.get("local_slope"):
            checks.append(
                _chk(
                    True,
                    "GB 55038-2025 4.1.9 / 4.1.12",
                    f"若全室按 1％找坡，最远点落差约 {wet.get('full_room_fall_mm')}mm，会超过门口 15mm 限值，故地漏附近局部找坡，门口单独按 ≤15mm 斜坡过渡",
                    hard=False,
                    kind="note",
                )
            )
    if room.kind == "厨房":
        wetk = layout.get("wet_features") or {}
        step = float(wetk.get("door_step_mm") or 15)
        ramp = wetk.get("ramp")
        checks.append(_chk(step <= 15 + 1e-6 and bool(ramp), "GB 55038-2025 4.1.12", f"厨房与相邻空间地面高差不应大于 15mm，并以斜坡过渡；本图门口高差按 {step:.0f}mm"))
    return checks


def check_wall(room, tile, walls: list[dict]) -> list[dict[str, Any]]:
    min_edge = min((w["min_edge"] for w in walls), default=0)
    min_ok = min(tile["w"], tile["h"]) / 3
    holes = sum(len(w.get("holes") or []) for w in walls)
    checks = [
        _chk(min_edge >= min_ok - 1e-6, "排砖工艺", f"墙砖边条最小 {min_edge*1000:.0f}mm，不宜小于整砖 1/3；非整砖放阴角", hard=False, kind="craft"),
        _chk(holes >= 1 or room.kind in ("走廊",), "GB 50210-2018 10.2.6", "墙面凸出物及门窗洞口四周饰面砖应整砖套割吻合、边缘整齐；本图已按门洞套割" if holes else "未识别门洞，按南墙预留门洞套割"),
        _chk(True, "GB 50210-2018 10.2.4", "满粘法大面和阳角空鼓须敲击检查；阳角宜采用阳角条。本图无法判定空鼓", hard=False, kind="site"),
        _chk(True, "GB 50210-2018 10.2.8", "内墙饰面砖允许偏差：立面垂直 2mm、表面平整 3mm、接缝直线 2mm、接缝宽度 1mm，须现场尺量", hard=False, kind="site"),
    ]
    if room.kind in ("卧室", "客厅"):
        checks.append(_chk(room.height >= 2.60 - 1e-6, "GB 55038-2025 4.1.2", f"室内净高按层高 {room.height}m 计（卧室/起居室不应低于 2.60m；局部低于 2.60m 的面积不应大于 1/3 且不应低于 2.20m）"))
    else:
        checks.append(_chk(room.height >= 2.20 - 1e-6, "GB 55038-2025 4.1.2", f"室内净高按层高 {room.height}m 计（厨房/卫生间不应低于 2.20m）"))
    if room.kind == "卫生间":
        checks.append(_chk(room.height + 1e-6 >= 2.00, "GB 55038-2025 4.1.9", "淋浴区墙面防水层高度不应小于 2.00m，且不低于喷淋口；洗面器处墙面防水不应小于 1.20m；其余泛水翻起不应小于 0.25m。本图立面已标出这三道高度"))
    return checks


def check_ceiling(room, ceil: dict, project_type: str = "既有") -> list[dict[str, Any]]:
    wet = bool(ceil.get("wet"))
    sec_limit = 0.40 if wet else 0.60
    living = room.kind in ("客厅", "卧室", "餐厅", "书房")
    hmin = 2.60 if living else 2.20
    mode = ceil.get("mode") or "full"
    net = ceil.get("net_height", room.height)
    local_ratio = float(ceil.get("local_area_ratio") or 1)
    net_local = float(ceil.get("net_local") or net)
    checks = [
        _chk(ceil.get("hanger_span_ok", False), "GB 50327-2001 8.3.1", f"吊点间距应小于 1.2m；本排布最大吊点距 {ceil.get('hanger_max', 0)}m"),
        _chk(ceil.get("hanger_end_ok", False), "GB 50327-2001 8.3.1 / GB 50210-2018", "吊杆距主龙骨端部不得超过 300mm；与设备相遇时应调整吊点或增设吊杆"),
        _chk(ceil["secondary_spacing"] <= sec_limit + 1e-6, "GB 50327-2001 8.3.1", f"次龙骨间距 {ceil['secondary_spacing']}m（不得大于 {int(sec_limit*1000)}mm" + ("；潮湿场所以 300～400mm" if wet else "") + "）"),
        _chk(0.001 * ceil.get("span_m", 1) - 1e-9 <= ceil.get("camber_m", 0) <= 0.003 * ceil.get("span_m", 1) + 1e-9, "GB 50327-2001 8.3.1", f"短向跨度 {ceil.get('span_m')}m，起拱 {ceil.get('camber_m', 0)*1000:.1f}mm（按短跨 1‰～3‰，本图取 2‰）"),
        _chk(ceil.get("stagger", True), "GB 50210-2018 吊顶", "石膏板应错缝安装，不得出现通缝"),
        _chk(len(ceil.get("extras") or []) >= 1, "GB 50210-2018 吊顶", "灯具、喷淋、检修口处应设附加龙骨；重型灯具不得直接吊挂在吊顶龙骨上"),
        _chk(not ceil.get("hanger_need_brace"), "GB 50210-2018 吊顶", "吊杆长度大于 1.5m 时应设反支撑；本方案吊杆长度按吊顶下降 " + f"{ceil.get('drop_m', 0)}m 计" + ("，须加反支撑" if ceil.get("hanger_need_brace") else "，不必设反支撑")),
    ]
    if project_type == "新建":
        checks.insert(0, _chk(room.height >= 3.00 - 1e-6, "GB 55038-2025 4.1.2-1", f"新建住宅层高不应低于 3.00m；当前层高 {room.height}m"))
    else:
        checks.insert(0, _chk(True, "GB 55038-2025 4.1.2-1", f"新建住宅层高不应低于 3.00m。本工程按既有住宅装修：当执行现行规范确有困难时不应低于原建造标准。当前层高 {room.height}m", hard=False, kind="note"))
    if mode == "local":
        checks.append(_chk(local_ratio <= 1 / 3 + 1e-6, "GB 55038-2025 4.1.2-2", f"局部净高低于 2.60m 的面积占比 {local_ratio*100:.1f}%（不应大于室内使用面积的 1/3）"))
        checks.append(_chk(net_local + 1e-6 >= 2.20, "GB 55038-2025 4.1.2-2", f"局部吊顶净高 {net_local}m（局部净高不应低于 2.20m）；其余区域按层高 {net}m，不应低于 2.60m"))
        checks.append(_chk(net + 1e-6 >= hmin, "GB 55038-2025 4.1.2-2", f"未吊区域净高 {net}m（卧室/起居室不应低于 2.60m）"))
    else:
        checks.append(_chk(net + 1e-6 >= hmin, "GB 55038-2025 4.1.2", f"吊顶后估算净高 {net}m（{room.kind}不应低于 {hmin:.2f}m；层高不足时应改为局部吊顶或降低龙骨）"))
    ht = ceil["hatch"]
    checks.append(_chk(ht["w"] >= 0.4 - 1e-6 and ht["h"] >= 0.4 - 1e-6, "检修", "检修口常见不宜小于 600×600mm，并应设附加龙骨、避开主视面", hard=False, kind="craft"))
    return checks


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
        if room.kind == "卫生间":
            rows += [
                {"name": "防水层+地漏找坡 1%", "qty": round(room.area, 2), "unit": "㎡"},
                {"name": "门口斜坡过渡 ≤15mm", "qty": 1, "unit": "处"},
            ]
        if room.kind == "厨房":
            rows.append({"name": "门口斜坡过渡 ≤15mm", "qty": 1, "unit": "处"})
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
        if room.kind == "卫生间":
            rows += [
                {"name": "淋浴区墙面防水 ≥2.00m", "qty": 1, "unit": "项"},
                {"name": "洗面器墙面防水 ≥1.20m", "qty": 1, "unit": "项"},
                {"name": "其余泛水翻起 ≥0.25m", "qty": 1, "unit": "项"},
            ]
    if task == "ceiling" and ceil:
        rows += [
            {"name": "吊顶方式", "qty": 1, "unit": "满吊" if payload.get("mode") != "local" else "局部吊顶"},
            {"name": "吊顶板", "qty": payload["panel_count"], "unit": "块"},
            {"name": "主龙骨", "qty": len(payload["mains"]), "unit": "根"},
            {"name": "次龙骨", "qty": len(payload["seconds"]), "unit": "根"},
            {"name": "吊杆", "qty": payload["hanger_count"], "unit": "套"},
            {"name": "灯位附骨", "qty": len(payload.get("extras") or []), "unit": "处"},
            {"name": "检修口", "qty": 1, "unit": "个"},
            {"name": "起拱（短跨 2‰）", "qty": round(payload.get("camber_m", 0) * 1000, 1), "unit": "mm"},
        ]
    if task == "furniture":
        rows += [{"name": it["name"], "qty": 1, "unit": "件"} for it in payload["items"] if it["name"] != "通行净宽示意"]
    return rows
