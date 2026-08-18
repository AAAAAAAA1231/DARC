from __future__ import annotations

import json
import re
from typing import Any

from jishubiao.config import RESOURCES


def load_catalog() -> dict[str, Any]:
    return json.loads((RESOURCES / "catalog.json").read_text(encoding="utf-8"))


def _tags_for(specialty_name: str, structure_name: str, residential: bool, extras: list[str]) -> set[str]:
    tags = {"all", specialty_name, structure_name}
    if residential or "住宅" in structure_name:
        tags.add("住宅")
    tags.update(extras)
    if "框剪" in structure_name or "框架剪力墙" in structure_name:
        tags.update({"框剪", "框架剪力墙", "混凝土"})
    if "剪力墙" in structure_name:
        tags.add("混凝土")
    if "框架" in structure_name:
        tags.add("混凝土")
    return {t for t in tags if t}


def select_codes(
    specialty: str,
    structure: str = "",
    residential: bool = False,
    extra_tags: list[str] | None = None,
    include_codes: list[str] | None = None,
    exclude_codes: list[str] | None = None,
) -> list[dict[str, str]]:
    cat = load_catalog()
    tags = _tags_for(specialty, structure, residential, extra_tags or [])
    exclude = {c.strip() for c in (exclude_codes or []) if c.strip()}
    picked: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in cat["codes"]:
        if not row.get("name"):
            continue
        code = row["code"]
        if code in exclude or code in seen:
            continue
        row_tags = set(row.get("tags") or [])
        if row_tags & tags or code in (include_codes or []):
            picked.append({"code": code, "name": row["name"], "kind": row.get("kind") or ""})
            seen.add(code)
    if include_codes:
        by_code = {r["code"]: r for r in cat["codes"] if r.get("name")}
        for code in include_codes:
            if code in seen or code in exclude:
                continue
            row = by_code.get(code)
            if row:
                picked.append({"code": row["code"], "name": row["name"], "kind": row.get("kind") or ""})
                seen.add(code)
    return picked


def parse_tender_flags(text: str) -> list[str]:
    text = text or ""
    flags: list[str] = []
    mapping = [
        (r"BIM|建筑信息模型", "BIM"),
        (r"装配式|装配率|PC构件|预制", "装配式"),
        (r"绿色建筑|星级绿色", "绿色建筑"),
        (r"海绵城市|海绵", "海绵城市"),
        (r"智慧工地|实名制|扬尘监测", "智慧工地"),
        (r"创优|鲁班奖|詹天佑|省优|市优", "创优"),
        (r"充电桩|新能源汽车", "充电桩"),
        (r"超低能耗|近零能耗", "超低能耗"),
        (r"基坑.*监测|深基坑", "深基坑"),
        (r"夜间施工|交通导改", "交通导改"),
    ]
    for pat, tag in mapping:
        if re.search(pat, text, flags=re.I):
            flags.append(tag)
    return flags


def _join_codes(codes: list[dict[str, str]], kinds: set[str] | None = None) -> str:
    rows = [c for c in codes if kinds is None or c.get("kind") in kinds]
    if not rows:
        rows = codes[:8]
    return "、".join(f"{c['code']}《{c['name']}》" for c in rows)


def _p(project: dict[str, Any], key: str, default: str = "（待补充）") -> str:
    v = str(project.get(key) or "").strip()
    return v if v else default


def generate_bid(project: dict[str, Any]) -> dict[str, Any]:
    specialty = _p(project, "specialty", "房屋建筑")
    structure = _p(project, "structure", "")
    residential = bool(project.get("residential")) or "住宅" in _p(project, "building_type", "")
    tender = str(project.get("tender_text") or "")
    flags = parse_tender_flags(tender + " " + _p(project, "notes", ""))
    extra_tags = list(flags)
    include = [c.strip() for c in (project.get("include_codes") or []) if str(c).strip()]
    exclude = [c.strip() for c in (project.get("exclude_codes") or []) if str(c).strip()]
    codes = select_codes(specialty, structure, residential, extra_tags, include, exclude)

    name = _p(project, "name", "××工程")
    loc = _p(project, "location")
    owner = _p(project, "owner", "招标人")
    bidder = _p(project, "bidder", "投标人")
    area = _p(project, "area")
    floors = _p(project, "floors")
    duration = _p(project, "duration", "按招标文件")
    seismic = _p(project, "seismic")
    foundation = _p(project, "foundation")
    cost = _p(project, "cost")
    quality_goal = _p(project, "quality_goal", "一次性验收合格")
    safety_goal = _p(project, "safety_goal", "杜绝较大及以上生产安全事故")

    mandatory = _join_codes(codes, {"强制性通用规范"})
    accept = _join_codes(codes, {"施工验收", "施工技术"})
    safety = _join_codes(codes, {"安全"})
    manage = _join_codes(codes, {"管理", "绿色施工"})

    chapters: list[dict[str, Any]] = []

    chapters.append(
        {
            "title": "第一章 编制说明与编制依据",
            "sections": [
                {
                    "heading": "1.1 编制说明",
                    "body": (
                        f"本技术标为{bidder}针对{name}施工投标编制的施工组织设计及技术标文件，"
                        f"工程地点位于{loc}，结构类型为{structure or '详见设计文件'}，建筑面积{area}，层数{floors}。"
                        f"编制目的是在满足招标文件、施工图及现行工程建设规范的前提下，明确施工部署、主要方案、质量安全与进度保证措施。"
                        f"质量目标：{quality_goal}。安全目标：{safety_goal}。计划工期：{duration}。"
                        "本文件引用规范均采用现行有效版本；若国家或地方在投标截止日后发布新的强制性条文，以新发布条文为准并办理设计/监理确认。"
                    ),
                    "codes": [],
                },
                {
                    "heading": "1.2 编制依据",
                    "body": (
                        "本技术标主要编制依据如下：\n"
                        f"（1）{name}招标文件、投标须知、技术标准和要求、答疑及补遗文件；\n"
                        "（2）施工图设计文件、地质勘察报告、工程测量成果；\n"
                        f"（3）强制性工程建设规范：{mandatory or '按工程类型选用 GB 55000 系列通用规范'}；\n"
                        f"（4）施工及验收标准：{accept}；\n"
                        f"（5）安全与现场管理标准：{safety}；\n"
                        f"（6）项目管理及绿色施工：{manage}；\n"
                        "（7）《中华人民共和国建筑法》《建设工程质量管理条例》《建设工程安全生产管理条例》及工程所在地建设行政主管部门有关文件。\n"
                        "引用时优先执行强制性通用规范；通用规范与推荐性标准不一致时，以通用规范的强制性要求为准。"
                    ),
                    "codes": [c["code"] for c in codes[:12]],
                },
            ],
        }
    )

    chapters.append(
        {
            "title": "第二章 工程概况",
            "sections": [
                {
                    "heading": "2.1 工程简介",
                    "body": (
                        f"工程名称：{name}。建设地点：{loc}。招标人：{owner}。投标人：{bidder}。\n"
                        f"专业类别：{specialty}。结构类型：{structure or '详见图纸'}。基础形式：{foundation}。"
                        f"抗震设防：{seismic}。建筑面积/规模：{area}。层数：{floors}。投资规模：{cost}。工期：{duration}。\n"
                        f"建设内容以招标文件及施工图为准。{('本工程含住宅功能，施工及验收同时执行 GB 55038-2025《住宅项目规范》相关要求。' if residential else '')}"
                    ),
                    "codes": ["GB 55031-2022"] if specialty == "房屋建筑" else [],
                },
                {
                    "heading": "2.2 建设条件与重难点",
                    "body": _difficulties(specialty, structure, foundation, flags, tender),
                    "codes": [],
                },
            ],
        }
    )

    chapters.append(_chapter_deploy(name, duration, specialty, flags))
    chapters.append(_chapter_scheme(specialty, structure, foundation, seismic, codes, flags))
    chapters.append(_chapter_progress(duration, specialty))
    chapters.append(_chapter_resource(specialty, area, duration))
    chapters.append(_chapter_quality(specialty, structure, quality_goal, codes))
    chapters.append(_chapter_safety(safety_goal, codes, specialty))
    chapters.append(_chapter_green(codes, flags))
    chapters.append(_chapter_season())
    chapters.append(_chapter_emergency(specialty))

    extra_ch = _flag_chapters(flags, codes)
    chapters.extend(extra_ch)

    if tender.strip():
        chapters.append(
            {
                "title": "第十三章 招标文件技术要求响应",
                "sections": [
                    {
                        "heading": "13.1 响应说明",
                        "body": (
                            "针对招标文件技术标准和要求，投标人逐条响应：凡招标文件明确的质量标准、工期、安全文明、创优、信息化、环保等条款，"
                            "均纳入项目经理部目标责任书，并由技术负责人组织交底。招标文件与现行强制性规范不一致时，按较严者执行并书面向招标人澄清。\n"
                            "招标文件摘录要点（由投标人填写原文后系统纳入）：\n"
                            + "\n".join(line.strip() for line in tender.strip().splitlines() if line.strip())
                        ),
                        "codes": [],
                    }
                ],
            }
        )

    warnings = [
        "本文件是按现行规范号和工程类型生成的技术标初稿，不能替代注册建造师/技术负责人签章审核。",
        "请用施工图、地勘、招标文件核对工期、机械、周转材料及危大工程清单后再递交。",
        "规范条文内容请以正式出版物或官方文本为准，本文只引用规范名称和号，不复制规范正文。",
    ]
    if any(x.get("old") in tender for x in load_catalog()["avoid_old"]):
        warnings.append("招标文件或备注中疑似出现已废止规范号，请改用现行版本。")

    toc = [ch["title"] for ch in chapters]
    return {
        "project": {
            "name": name,
            "location": loc,
            "owner": owner,
            "bidder": bidder,
            "specialty": specialty,
            "structure": structure,
            "residential": residential,
            "area": area,
            "floors": floors,
            "duration": duration,
            "seismic": seismic,
            "foundation": foundation,
        },
        "flags": flags,
        "codes": codes,
        "toc": toc,
        "chapters": chapters,
        "warnings": warnings,
    }


def _difficulties(specialty: str, structure: str, foundation: str, flags: list[str], tender: str) -> str:
    items = [
        f"基础形式为{foundation or '详见地勘'}，施工前应核对地下水、支护与降水方案，执行 GB 55003-2021、GB 50202-2018。",
        f"主体结构为{structure or specialty}，施工缝、后浇带、垂直度及关键节点是质量控制重点。",
        "总平面受场地限制时，材料周转、垂直运输与周边管线保护需专项方案。",
    ]
    if "深基坑" in flags or "基坑" in (tender or ""):
        items.append("深基坑属于危大工程，执行住房和城乡建设部危大工程管理规定，编制专项施工方案并按规定论证。")
    if specialty in {"市政道路", "公路工程"}:
        items.append("开放交通或半封闭施工时，导改、夜间作业和成品保护是进度与安全的主要矛盾。")
    if specialty == "市政给排水":
        items.append("管道工程重点控制轴线、高程、接口严密性及与现状管线交叉，闭水/闭气试验按 GB 50268-2008。")
    if "装配式" in flags:
        items.append("装配式构件运输、存放、吊装和灌浆是质量关键，执行 GB/T 51226-2017、JGJ 1-2014。")
    return "\n".join(f"（{i}）{t}" for i, t in enumerate(items, 1))


def _chapter_deploy(name: str, duration: str, specialty: str, flags: list[str]) -> dict[str, Any]:
    return {
        "title": "第三章 施工部署",
        "sections": [
            {
                "heading": "3.1 总体思路",
                "body": (
                    f"{name}按“先地下后地上、先主体后装饰、先结构后机电、分区流水、立体交叉”组织施工。"
                    f"总工期{duration}，划分为准备、基础、主体、装饰机电、收尾验收等阶段。"
                    "项目经理部设项目经理、技术负责人、生产经理、质量员、安全员、机械员、材料员、资料员，岗位职责按 GB/T 50326-2017 界定。"
                    + (" 本工程同步部署智慧工地：实名制、塔吊/升降机监测、扬尘与噪音在线监测。" if "智慧工地" in flags else "")
                ),
                "codes": ["GB/T 50326-2017"],
            },
            {
                "heading": "3.2 区段划分",
                "body": (
                    "按设计后浇带、沉降缝或道路桩号划分施工段，每段配齐木工、钢筋、混凝土（或路面、管道）班组，形成节奏流水。"
                    f"{'市政、公路工程按桩号及交通导改阶段划分工作面。' if specialty in {'市政道路', '公路工程'} else '房屋建筑按楼层、单元划分竖向流水。'}"
                ),
                "codes": [],
            },
        ],
    }


def _chapter_scheme(
    specialty: str,
    structure: str,
    foundation: str,
    seismic: str,
    codes: list[dict[str, str]],
    flags: list[str],
) -> dict[str, Any]:
    sections: list[dict[str, Any]] = []
    if specialty in {"房屋建筑", "钢结构厂房"}:
        sections.append(
            {
                "heading": "4.1 测量放线",
                "body": (
                    "平面控制网与高程控制网按 GB 55018-2021《工程测量通用规范》建立，使用校检合格的全站仪、水准仪。"
                    "建筑物定位以规划红线及设计坐标为准，轴线传递采用内控法，每层复测垂直度。"
                    "沉降观测点按设计及地勘要求埋设，资料纳入竣工档案。"
                ),
                "codes": ["GB 55018-2021"],
            }
        )
        sections.append(
            {
                "heading": "4.2 地基与基础",
                "body": (
                    f"基础形式为{foundation or '按图施工'}。土方开挖按放坡或支护方案进行，基底保护层预留人工清底。"
                    "验槽执行 GB 55003-2021、GB 50202-2018，地勘单位、设计、监理、施工四方参加。"
                    "垫层、防水、钢筋、混凝土施工缝处理符合设计；地下防水执行 GB 55030-2022、GB 50108-2008、GB 50208-2011。"
                    "回填分层压实，取样检测。基坑周边堆载、降水对周边建（构）筑物的影响纳入监测。"
                ),
                "codes": ["GB 55003-2021", "GB 50202-2018", "GB 55030-2022"],
            }
        )
        if "钢" in (structure or specialty):
            sections.append(
                {
                    "heading": "4.3 钢结构安装",
                    "body": (
                        "钢构件进场核验质量证明文件、焊缝探伤报告及高强度螺栓批号。安装执行 GB 55006-2021、GB 50755-2012、GB 50205-2020。"
                        "焊接执行 GB 50661-2011，高强度螺栓执行 JGJ 82-2011，初拧终拧扭矩有记录。"
                        "吊装设警戒区，执行 JGJ 80-2016。主体完成后按设计做防腐防火涂装，涂层厚度检测。"
                    ),
                    "codes": ["GB 55006-2021", "GB 50755-2012", "GB 50205-2020", "GB 50661-2011"],
                }
            )
        else:
            sections.append(
                {
                    "heading": "4.3 主体结构（混凝土）",
                    "body": (
                        f"主体为{structure or '混凝土结构'}，抗震设防{seismic or '按设计'}。"
                        "执行 GB 55008-2021、GB 50666-2011、GB 50204-2015。"
                        "钢筋进场复试，接头优先机械连接（JGJ 107-2016）或焊接（JGJ 18-2012），接头位置满足设计及抗震构造。"
                        "模板及支架执行 JGJ 162-2008，承重架按危大工程管理；混凝土浇筑连续，施工缝留在受力较小部位，振捣密实，覆盖养护。"
                        "同条件试块用于拆模与吊装依据。竖向构件垂直度、层高、截面偏差按 GB 50204-2015 允许偏差控制。"
                    ),
                    "codes": ["GB 55008-2021", "GB 50666-2011", "GB 50204-2015", "JGJ 107-2016"],
                }
            )
        sections.append(
            {
                "heading": "4.4 砌体、屋面、装饰与机电",
                "body": (
                    "填充墙砌筑执行 GB 50924-2014、GB 50203-2011，与主体连接按抗震构造（拉结筋或植筋）。"
                    "屋面与防水执行 GB 50207-2012、GB 55030-2022。装饰装修执行 GB 50210-2018，地面执行 GB 50209-2010。"
                    "给排水、电气、通风执行 GB 50242-2002、GB 50303-2015、GB 50243-2016；节能做法执行 GB 55015-2021、GB 50411-2019。"
                    "防火分区、消防设施不得因施工改变，执行 GB 55037-2022、GB 50016-2014（2018年版）。"
                ),
                "codes": ["GB 50210-2018", "GB 55015-2021", "GB 55037-2022"],
            }
        )
    elif specialty == "装饰装修":
        sections.append(
            {
                "heading": "4.1 装饰装修方案",
                "body": (
                    "进场后复核基层平整度、强度及防水节点。吊顶、隔墙、饰面砖、幕墙（如有）分项执行 GB 50210-2018。"
                    "室内环境污染物控制符合民用建筑相关标准。电气及消防改造不得降低原防火分区和疏散宽度，执行 GB 55037-2022。"
                    "易燃材料限量进场，执行 GB 50720-2011。"
                ),
                "codes": ["GB 50210-2018", "GB 55037-2022", "GB 50720-2011"],
            }
        )
    elif specialty == "市政道路":
        sections.append(
            {
                "heading": "4.1 路基与路面",
                "body": (
                    "测量放线按桩号控制。路基压实度、弯沉按 CJJ 1-2008 检验。"
                    "基层、面层材料进场复试，摊铺温度、碾压遍数、接缝处理按技术方案执行。"
                    "雨水口、检查井与路面衔接平顺，井周回填密实。交通导改、夜间施工设专项方案。"
                ),
                "codes": ["CJJ 1-2008"],
            }
        )
    elif specialty == "市政给排水":
        sections.append(
            {
                "heading": "4.1 管道开槽与安装",
                "body": (
                    "沟槽支护、降水和管基处理按设计及 GB 50268-2008。管道轴线、高程允许偏差按规范检验。"
                    "接口、防腐、井室砌筑或现浇一次到位。压力管道强度及严密性试验、无压管道闭水试验按 GB 50268-2008 执行。"
                    "与现状管线交叉先探明再开挖。城镇排水系统不得降低原有排水能力，执行 GB 55033-2022。"
                ),
                "codes": ["GB 50268-2008", "GB 55033-2022"],
            }
        )
    else:
        sections.append(
            {
                "heading": "4.1 路基桥涵与路面",
                "body": (
                    "路基执行 JTG/T 3610-2019，桥涵执行 JTG/T 3650-2020，沥青路面执行 JTG F40-2004，质量评定执行 JTG F80/1-2017。"
                    "安全执行 JTG/T 3360-01-2018。软基处理、高边坡、梁板预制吊装等按专项方案实施。"
                ),
                "codes": ["JTG/T 3610-2019", "JTG/T 3650-2020", "JTG F80/1-2017"],
            }
        )
    if "装配式" in flags:
        sections.append(
            {
                "heading": "4.5 装配式专项",
                "body": (
                    "构件生产、运输、存放、吊装、支撑、套筒灌浆及接缝防水执行 GB/T 51226-2017、JGJ 1-2014。"
                    "灌浆料、套筒见证取样，灌浆全过程可追溯。吊装作业执行 JGJ 80-2016。"
                ),
                "codes": ["GB/T 51226-2017", "JGJ 1-2014"],
            }
        )
    return {"title": "第四章 主要施工方案", "sections": sections}


def _chapter_progress(duration: str, specialty: str) -> dict[str, Any]:
    return {
        "title": "第五章 施工进度计划",
        "sections": [
            {
                "heading": "5.1 进度安排",
                "body": (
                    f"总工期按招标文件为{duration}。投标人编制一级网络计划和月度计划，关键线路为基础→主体（或路基路面）→装饰机电（或交通开放）→验收。"
                    "劳动力、材料、机械配置与计划同步。延误预警超过 3 天启动纠偏：增加班组、调整流水段或报监理确认的工序优化。"
                    "节点完成以验收资料为准，不得以形象进度代替质量验收。"
                ),
                "codes": ["GB/T 50326-2017"],
            }
        ],
    }


def _chapter_resource(specialty: str, area: str, duration: str) -> dict[str, Any]:
    return {
        "title": "第六章 资源配置计划",
        "sections": [
            {
                "heading": "6.1 劳动力与机械",
                "body": (
                    f"按面积/规模{area}、工期{duration}配置劳务队伍，特殊工种持证上岗。"
                    f"{'房屋类工程主要机械：塔式起重机、施工升降机、混凝土泵车、钢筋加工设备、发电机。' if specialty in {'房屋建筑', '钢结构厂房'} else '线性工程主要机械：挖掘机、装载机、压路机、摊铺机、吊车、水泵。'}"
                    "大型机械安装拆卸、起重吊装列入危大工程清单。机械使用执行 JGJ 33-2012，临时用电执行 JGJ 46-2005。"
                ),
                "codes": ["JGJ 33-2012", "JGJ 46-2005"],
            }
        ],
    }


def _chapter_quality(specialty: str, structure: str, goal: str, codes: list[dict[str, str]]) -> dict[str, Any]:
    accept = _join_codes(codes, {"施工验收", "强制性通用规范"})
    return {
        "title": "第七章 质量保证体系与措施",
        "sections": [
            {
                "heading": "7.1 质量目标与体系",
                "body": (
                    f"质量目标：{goal}。建立项目质量责任制，执行 GB 55032-2022《建筑与市政工程施工质量控制通用规范》及 {accept}。"
                    "实行材料进场验收、工序三检、隐蔽验收、检测试验计划。见证取样送具备资质的检测机构。"
                    "混凝土、钢筋、防水、焊接、螺栓、管道接口等关键工序设置质量控制点。"
                ),
                "codes": ["GB 55032-2022", "GB 50300-2013"],
            },
            {
                "heading": "7.2 通病防治",
                "body": (
                    "重点防治：钢筋位移、保护层不足、混凝土蜂窝孔洞裂缝、砌体通缝、防水渗漏、地面空鼓、栏杆高度不足、管道返坡、路面裂缝与井框高差。"
                    "对涉及结构安全、防火、节能的部位，按强制性条文检查，不得采用“经验做法”替代规范。"
                ),
                "codes": ["GB 55008-2021", "GB 55037-2022"],
            },
        ],
    }


def _chapter_safety(goal: str, codes: list[dict[str, str]], specialty: str) -> dict[str, Any]:
    return {
        "title": "第八章 安全文明施工",
        "sections": [
            {
                "heading": "8.1 安全生产",
                "body": (
                    f"安全目标：{goal}。现场按 JGJ 59-2011 检查，高处作业执行 JGJ 80-2016，临时用电执行 JGJ 46-2005，机械执行 JGJ 33-2012。"
                    "脚手架执行 JGJ 130-2011 或盘扣架相关标准。消防执行 GB 50720-2011、GB 55037-2022。"
                    "危大工程按住房和城乡建设部有关规定编制专项方案，超过一定规模的办理专家论证。每日班前教育，每周安全例会。"
                ),
                "codes": ["JGJ 59-2011", "JGJ 80-2016", "JGJ 46-2005", "GB 50720-2011"],
            },
            {
                "heading": "8.2 文明施工与环境卫生",
                "body": (
                    "执行 JGJ 146-2013。工地围挡、大门、冲洗、覆盖、硬化到位；建筑垃圾分类；食堂、宿舍、厕所符合卫生要求。"
                    "扬尘、噪音控制满足工程所在地规定。夜间施工办理手续。"
                ),
                "codes": ["JGJ 146-2013"],
            },
        ],
    }


def _chapter_green(codes: list[dict[str, str]], flags: list[str]) -> dict[str, Any]:
    extra = " 若招标文件要求绿色建筑等级，施工过程资料按 GB/T 50378-2019 对应条款收集。" if "绿色建筑" in flags else ""
    return {
        "title": "第九章 绿色施工与环境保护",
        "sections": [
            {
                "heading": "9.1 绿色施工",
                "body": (
                    "执行 GB/T 50905-2014，从节地、节能、节材、节水、环境保护组织施工。周转材料优先定型化、工具化；照明分区控制；雨水收集用于降尘。"
                    "废弃物分类，有毒有害废物交有资质单位。节能分项验收执行 GB 55015-2021、GB 50411-2019。"
                    + extra
                ),
                "codes": ["GB/T 50905-2014", "GB 55015-2021"],
            }
        ],
    }


def _chapter_season() -> dict[str, Any]:
    return {
        "title": "第十章 季节性施工",
        "sections": [
            {
                "heading": "10.1 雨期、高温与冬期",
                "body": (
                    "雨期：基坑排水、覆盖、防坍塌；混凝土浇筑避开暴雨或采取防雨棚；电气设备防潮漏电。"
                    "高温：避开正午浇筑，掺缓凝组分并加强保湿养护。"
                    "冬期：混凝土受冻临界强度按 GB 50666-2011 控制，采用综合蓄热或暖棚，禁止未掺防冻组分的负温浇筑。"
                    "六级以上大风停止起重吊装。台风、暴雨按应急预案撤离。"
                ),
                "codes": ["GB 50666-2011"],
            }
        ],
    }


def _chapter_emergency(specialty: str) -> dict[str, Any]:
    return {
        "title": "第十一章 应急预案要点",
        "sections": [
            {
                "heading": "11.1 应急组织",
                "body": (
                    "成立应急领导小组，项目经理为现场第一责任人。针对坍塌、触电、高处坠落、火灾、物体打击、机械伤害、管线破坏"
                    f"{'、道路交通事故' if specialty in {'市政道路', '公路工程'} else ''}编制预案，储备急救药品、灭火器、应急灯、备用泵。"
                    "每季度演练一次，事故报告时限执行国家及地方规定。"
                ),
                "codes": ["GB 50720-2011"],
            }
        ],
    }


def _flag_chapters(flags: list[str], codes: list[dict[str, str]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if "BIM" in flags:
        out.append(
            {
                "title": "专项：BIM 应用",
                "sections": [
                    {
                        "heading": "BIM 实施",
                        "body": (
                            "执行 GB/T 51269-2017、GB/T 51301-2018。投标阶段提交模型应用点：管线综合、进度模拟、危大工程可视化交底。"
                            "模型与施工图冲突提前提出，经设计确认后实施。竣工提交与现场一致的竣工模型及资料。"
                        ),
                        "codes": ["GB/T 51269-2017", "GB/T 51301-2018"],
                    }
                ],
            }
        )
    if "智慧工地" in flags:
        out.append(
            {
                "title": "专项：智慧工地",
                "sections": [
                    {
                        "heading": "信息化手段",
                        "body": "实名制闸机、视频监控、扬尘噪音监测、塔吊/升降机黑匣子、危大工程旁站记录电子化，数据保存至竣工验收。",
                        "codes": [],
                    }
                ],
            }
        )
    if "创优" in flags:
        out.append(
            {
                "title": "专项：创优策划",
                "sections": [
                    {
                        "heading": "创优路径",
                        "body": "对照拟创奖项申报条件编制创优计划，样板引路，过程资料同步收集。质量验收一次合格率、观感、档案深度按创优标准加严，且不得低于强制性规范。",
                        "codes": ["GB 50300-2013"],
                    }
                ],
            }
        )
    if "海绵城市" in flags:
        out.append(
            {
                "title": "专项：海绵城市",
                "sections": [
                    {
                        "heading": "海绵设施施工",
                        "body": "透水铺装、雨水花园、调蓄设施按设计控制标高、级配和防渗。施工期间保护已完海绵设施，避免泥浆堵塞。验收按设计及地方海绵城市技术导则。",
                        "codes": [],
                    }
                ],
            }
        )
    return out
