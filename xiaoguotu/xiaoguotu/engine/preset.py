from __future__ import annotations

from typing import Any


MODES = [
    {"id": "interior", "name": "室内效果图", "max_view": "Camera_Interior", "desc": "室内人视透视，对标 3ds Max 室内相机"},
    {"id": "exterior", "name": "大楼外观", "max_view": "Camera_Exterior_34", "desc": "三点透视街景/人视外观"},
    {"id": "siteplan", "name": "整体平面", "max_view": "Camera_Axon_Site", "desc": "场地轴测/总平面效果"},
    {"id": "aerial", "name": "鸟瞰效果图", "max_view": "Camera_Aerial", "desc": "高空 45° 鸟瞰"},
    {"id": "night", "name": "夜景外观", "max_view": "Camera_Night", "desc": "夜间外观，窗光+环境照明"},
]

BUILDING_TYPES = {
    "办公楼": {"floors": 18, "floor_h": 3.6, "length": 48, "width": 24, "style": "curtain", "interior": "办公室"},
    "住宅": {"floors": 11, "floor_h": 2.9, "length": 36, "width": 15, "style": "paint", "interior": "客厅"},
    "商业": {"floors": 6, "floor_h": 4.5, "length": 60, "width": 32, "style": "stone", "interior": "大堂"},
    "酒店": {"floors": 22, "floor_h": 3.3, "length": 42, "width": 22, "style": "curtain", "interior": "大堂"},
    "学校": {"floors": 6, "floor_h": 3.6, "length": 72, "width": 18, "style": "paint", "interior": "教室"},
    "医院": {"floors": 12, "floor_h": 3.6, "length": 54, "width": 28, "style": "stone", "interior": "门厅"},
}

TIMES = {
    "清晨": {"az": 95, "alt": 12, "exposure": 1.15, "sky": "#c9d7ea", "sun": 2.2, "kelvin": 5200},
    "上午": {"az": 135, "alt": 38, "exposure": 1.0, "sky": "#87b5e0", "sun": 3.0, "kelvin": 5500},
    "正午": {"az": 180, "alt": 62, "exposure": 0.85, "sky": "#6ea4d8", "sun": 3.6, "kelvin": 5700},
    "黄昏": {"az": 250, "alt": 8, "exposure": 1.25, "sky": "#e8a06a", "sun": 2.4, "kelvin": 3200},
    "夜晚": {"az": 210, "alt": -8, "exposure": 1.6, "sky": "#0b1220", "sun": 0.05, "kelvin": 4100},
}

LENSES = {
    "室内效果图": 35,
    "大楼外观": 24,
    "整体平面": 50,
    "鸟瞰效果图": 24,
    "夜景外观": 24,
}

OUTPUTS = [
    {"id": "1080p", "w": 1920, "h": 1080, "label": "1920×1080 (效果图常用)"},
    {"id": "2k", "w": 2560, "h": 1440, "label": "2560×1440"},
    {"id": "4k", "w": 3840, "h": 2160, "label": "3840×2160 (出图)"},
    {"id": "a3", "w": 1754, "h": 1240, "label": "A3 横图 150dpi"},
]


def _f(v: Any, d: float) -> float:
    try:
        n = float(v)
        return n if n > 0 else d
    except (TypeError, ValueError):
        return d


def _i(v: Any, d: int) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return d


def catalogs() -> dict[str, Any]:
    return {
        "modes": MODES,
        "building_types": list(BUILDING_TYPES.keys()),
        "times": list(TIMES.keys()),
        "outputs": OUTPUTS,
        "facades": ["涂料", "石材", "玻璃幕墙", "铝板", "砖墙"],
        "interiors": ["客厅", "办公室", "大堂", "卧室", "教室", "门厅"],
        "styles": ["现代", "新中式", "简欧"],
        "quality": ["草图 Draft", "中等 Medium", "成图 High"],
        "defaults": default_params("exterior"),
    }


def default_params(mode_id: str = "exterior") -> dict[str, Any]:
    mode = next((m for m in MODES if m["id"] == mode_id), MODES[1])
    b = BUILDING_TYPES["办公楼"]
    time_name = "夜晚" if mode_id == "night" else ("上午" if mode_id != "interior" else "上午")
    return {
        "mode": mode["id"],
        "name": "××办公楼效果图",
        "building_type": "办公楼",
        "floors": b["floors"],
        "floor_h": b["floor_h"],
        "length": b["length"],
        "width": b["width"],
        "facade": "玻璃幕墙" if b["style"] == "curtain" else "涂料",
        "interior_room": b["interior"],
        "interior_style": "现代",
        "time": time_name,
        "lens_mm": LENSES[mode["name"]],
        "camera_h": 1.6 if mode_id == "interior" else (1.7 if mode_id in ("exterior", "night") else 80),
        "two_point": True,
        "output": "1080p",
        "quality": "成图 High",
        "renderer": "V-Ray 6",
        "entourage": True,
        "bloom": mode_id == "night",
    }


def build_scene(data: dict[str, Any]) -> dict[str, Any]:
    mode_id = str(data.get("mode") or "exterior")
    mode = next((m for m in MODES if m["id"] == mode_id), MODES[1])
    btype = str(data.get("building_type") or "办公楼")
    base = BUILDING_TYPES.get(btype, BUILDING_TYPES["办公楼"])
    floors = max(1, min(80, _i(data.get("floors"), base["floors"])))
    floor_h = _f(data.get("floor_h"), base["floor_h"])
    length = _f(data.get("length"), base["length"])
    width = _f(data.get("width"), base["width"])
    height = floors * floor_h + 1.5
    time_name = str(data.get("time") or ("夜晚" if mode_id == "night" else "上午"))
    if mode_id == "night":
        time_name = "夜晚"
    env = TIMES.get(time_name, TIMES["上午"])
    lens = _i(data.get("lens_mm"), LENSES[mode["name"]])
    out_id = str(data.get("output") or "1080p")
    out = next((o for o in OUTPUTS if o["id"] == out_id), OUTPUTS[0])
    quality = str(data.get("quality") or "成图 High")
    samples = {"草图 Draft": (1, 8, 0.05), "中等 Medium": (1, 16, 0.02), "成图 High": (1, 24, 0.01)}.get(quality, (1, 24, 0.01))
    facade = str(data.get("facade") or ("玻璃幕墙" if base["style"] == "curtain" else "涂料"))
    cam_h = _f(data.get("camera_h"), 1.6 if mode_id == "interior" else 1.7)
    if mode_id == "aerial":
        cam_h = max(cam_h, height * 1.8)
    if mode_id == "siteplan":
        cam_h = max(cam_h, height * 2.4)

    fov = 2 * 180 / 3.14159265 * _atan(18.0 / max(lens, 1))  # 36mm film, half height 18
    scene = {
        "name": str(data.get("name") or f"××{btype}效果图"),
        "mode": mode,
        "building": {
            "type": btype,
            "floors": floors,
            "floor_h": floor_h,
            "length": length,
            "width": width,
            "height": round(height, 2),
            "facade": facade,
            "podium_h": 6.0 if floors >= 10 else 0.0,
        },
        "interior": {
            "room": str(data.get("interior_room") or base["interior"]),
            "style": str(data.get("interior_style") or "现代"),
        },
        "camera": {
            "name": mode["max_view"],
            "type": "VRay Physical Camera" if mode_id != "siteplan" else "VRay Physical Camera (Ortho-ish Axon)",
            "lens_mm": lens,
            "film": "36×24 mm",
            "fov_deg": round(fov, 1),
            "height_m": round(cam_h, 2),
            "target_h": 1.5 if mode_id in ("interior", "exterior", "night") else height * 0.35,
            "two_point": bool(data.get("two_point", True)),
            "f_stop": 8.0 if mode_id != "interior" else 5.6,
            "shutter": "1/125s" if time_name not in ("夜晚", "黄昏") else "1/50s",
            "iso": 100 if time_name not in ("夜晚",) else 400,
            "white_balance": env["kelvin"],
            "exposure": env["exposure"],
            "vignetting": 1.0,
        },
        "sun": {
            "type": "VRaySun + VRaySky",
            "time": time_name,
            "azimuth": env["az"],
            "altitude": env["alt"],
            "intensity": env["sun"],
            "turbidity": 2.5 if time_name != "黄昏" else 3.5,
            "size_mult": 1.0,
            "sky": env["sky"],
            "kelvin": env["kelvin"],
        },
        "gi": {
            "primary": "Brute Force",
            "secondary": "Light Cache",
            "subdivs": 16 if "High" in quality else 8,
            "light_cache_subdivs": 1500 if "High" in quality else 800,
        },
        "sampler": {
            "type": "Bucket",
            "min": samples[0],
            "max": samples[1],
            "noise": samples[2],
        },
        "output": {
            "width": out["w"],
            "height": out["h"],
            "label": out["label"],
            "format": "PNG 8bit sRGB",
            "filter": "Area",
            "color_mapping": "Reinhard",
            "burn": 0.75,
        },
        "quality": quality,
        "renderer": str(data.get("renderer") or "V-Ray 6"),
        "units": {"system": "毫米", "display": "毫米", "max_system_unit": "1 unit = 1 mm"},
        "entourage": bool(data.get("entourage", True)),
        "bloom": bool(data.get("bloom", mode_id == "night")),
        "max_sheet": "",
        "notes": [
            "本机实时预览按 3ds Max + V-Ray 常用效果图相机/灯光/出图参数生成场景。",
            "导出 PNG 为实时光栅效果图；同时给出可粘贴到 3ds Max 的参数单，便于用同一套设置出正式图。",
            "正式照片级成图仍需在 3ds Max 中替换成精细模型、真实材质与 HDRI。",
        ],
    }
    scene["max_sheet"] = render_max_sheet(scene)
    return scene


def _atan(x: float) -> float:
    import math
    return math.atan(x)


def render_max_sheet(scene: dict[str, Any]) -> str:
    c, s, b, o, g, sm = scene["camera"], scene["sun"], scene["building"], scene["output"], scene["gi"], scene["sampler"]
    return f"""3ds Max / V-Ray 效果图参数单
工程：{scene['name']}
模式：{scene['mode']['name']}（相机 {c['name']}）
渲染器：{scene['renderer']}

[单位]
系统单位 = {scene['units']['system']}
显示单位 = {scene['units']['display']}
{scene['units']['max_system_unit']}

[场景比例]
建筑 = {b['type']}  {b['length']}m × {b['width']}m × {b['height']}m
层数 = {b['floors']} × 层高 {b['floor_h']}m
外立面 = {b['facade']}
室内房间 = {scene['interior']['room']} / {scene['interior']['style']}

[相机] Physical Camera / VRay Physical Camera
镜头 = {c['lens_mm']} mm
胶片门 = {c['film']}
FOV ≈ {c['fov_deg']}°
相机高度 = {c['height_m']} m
目标高度 = {c['target_h']} m
两点透视（竖直校正）= {'开' if c['two_point'] else '关'}
光圈 f = {c['f_stop']}
快门 = {c['shutter']}
ISO = {c['iso']}
白平衡 = {c['white_balance']} K
曝光补偿 = {c['exposure']}
暗角 = {c['vignetting']}

[日光]
VRaySun 方位角 = {s['azimuth']}°
VRaySun 高度角 = {s['altitude']}°
强度倍数 = {s['intensity']}
浑浊度 turbidity = {s['turbidity']}
太阳尺寸 = {s['size_mult']}
VRaySky 开，时段 = {s['time']}

[GI / 采样]
初级 GI = {g['primary']}  subdivs {g['subdivs']}
次级 GI = {g['secondary']}  subdivs {g['light_cache_subdivs']}
图像采样器 = {sm['type']}
最小/最大细分 = {sm['min']} / {sm['max']}
噪波阈值 = {sm['noise']}
颜色映射 = {o['color_mapping']}  burn {o['burn']}

[出图]
尺寸 = {o['width']} × {o['height']}  ({o['label']})
格式 = {o['format']}
抗锯齿过滤 = {o['filter']}
质量档 = {scene['quality']}

[建议图层]
0-建筑主体 / 1-幕墙玻璃 / 2-室内可见家具 / 3-场地道路绿化 / 4-配景人车树 / 5-相机灯光
"""
