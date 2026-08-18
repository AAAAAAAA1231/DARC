from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from suanli_budget.config import RESOURCES


def load_catalog() -> dict[str, Any]:
    return json.loads((RESOURCES / "catalog.json").read_text(encoding="utf-8"))


def _gpu(catalog: dict[str, Any], gpu_id: str) -> dict[str, Any]:
    for g in catalog["gpus"]:
        if g["id"] == gpu_id:
            return g
    raise ValueError(f"未找到 GPU 型号：{gpu_id}")


def _f(v: Any, default: float = 0.0) -> float:
    try:
        if v in (None, ""):
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _line(name: str, qty: float, unit: str, price: float, spec: str = "") -> dict[str, Any]:
    amount = round(qty * price, 2)
    return {
        "name": name,
        "spec": spec,
        "qty": qty,
        "unit": unit,
        "price": round(price, 2),
        "amount": amount,
    }


def compile_budget(req: dict[str, Any], catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    catalog = catalog or load_catalog()
    d0 = dict(catalog.get("defaults") or {})
    d0.update({k: v for k, v in (req.get("prices") or {}).items() if v not in (None, "")})
    gpu = dict(_gpu(catalog, str(req.get("gpu_id") or "h20-141")))
    gpu.update({k: v for k, v in (req.get("gpu") or {}).items() if v not in (None, "")})

    cards_per_node = max(int(_f(gpu.get("cards_per_node"), 8)), 1)
    tflops = max(_f(gpu.get("fp16_tflops"), 1.0), 0.001)
    mode = str(req.get("mode") or "pflops")
    if mode == "count":
        want_gpu = max(int(_f(req.get("gpu_count"), 8)), 1)
    else:
        target = max(_f(req.get("target_pflops"), 1.0), 0.001)
        want_gpu = int(math.ceil(target * 1000.0 / tflops))
    nodes = int(math.ceil(want_gpu / cards_per_node))
    gpu_buy = nodes * cards_per_node
    pflops = gpu_buy * tflops / 1000.0

    price_mode = gpu.get("price_mode") or "node"
    if price_mode == "card":
        node_price = _f(gpu.get("card_price")) * cards_per_node
        card_price = _f(gpu.get("card_price"))
    else:
        node_price = _f(gpu.get("node_price"))
        card_price = node_price / cards_per_node if cards_per_node else 0.0

    cooling = str(req.get("cooling") or "liquid")
    pue = _f(d0.get("pue_liquid") if cooling == "liquid" else d0.get("pue_air"))
    rack_price = _f(d0.get("rack_price_liquid") if cooling == "liquid" else d0.get("rack_price_air"))
    cool_price = _f(d0.get("cooling_liquid_cny_per_kw") if cooling == "liquid" else d0.get("cooling_air_cny_per_kw"))

    cpu_n = nodes * int(_f(d0.get("cpu_per_node"), 2))
    ram_tb = nodes * _f(d0.get("ram_tb_per_node"), 2)
    nvme_tb = nodes * _f(d0.get("nvme_tb_per_node"), 16)
    nics = gpu_buy * int(_f(d0.get("nic_per_gpu"), 1))
    ports = max(int(_f(d0.get("ib_ports_per_switch"), 40)), 1)
    switches = int(math.ceil(nics / ports)) if nics else 0
    racks = int(math.ceil(nodes / max(_f(d0.get("nodes_per_rack"), 4), 1)))
    area = racks * _f(d0.get("m2_per_rack"), 6)

    it_kw = (
        gpu_buy * _f(gpu.get("tdp_w"), 400)
        + cpu_n * _f(d0.get("cpu_tdp_w"), 350)
        + nodes * _f(d0.get("other_node_w"), 400)
    ) / 1000.0
    facility_kw = it_kw * pue
    cooling_kw = max(it_kw, it_kw * max(pue - 1.0, 0.15))
    ups_kva = facility_kw * 1.25

    server = [
        _line("GPU 训练/推理服务器", nodes, "台", node_price, f"{gpu.get('name')}，每台 {cards_per_node} 卡"),
        _line("CPU（服务器内）", cpu_n, "颗", _f(d0.get("cpu_price")), "已含在整机价时请把单价改 0"),
        _line("内存", ram_tb, "TB", _f(d0.get("ram_price_per_tb")), "已含在整机价时请把单价改 0"),
        _line("本地 NVMe", nvme_tb, "TB", _f(d0.get("nvme_price_per_tb")), "节点缓存盘"),
    ]
    # If using node_price, CPU/RAM often included — default include_cpu_ram False when node mode
    include_cpu_ram = bool(req.get("include_cpu_ram", False))
    if not include_cpu_ram and price_mode == "node":
        server = [server[0], server[3]]

    network = [
        _line("高速网卡（每卡一张）", nics, "块", _f(d0.get("nic_price")), "IB/RoCE"),
        _line("高速交换机", switches, "台", _f(d0.get("ib_switch_price")), f"{ports} 口/台"),
        _line("高速线缆", nics, "根", _f(d0.get("cable_price")), "AOC/DAC"),
    ]
    facility = [
        _line("机柜", racks, "套", rack_price, "液冷" if cooling == "liquid" else "风冷"),
        _line("PDU", racks, "套", _f(d0.get("pdu_price"))),
        _line("UPS/配电（按 kVA）", round(ups_kva, 1), "kVA", _f(d0.get("ups_cny_per_kva"))),
        _line("制冷系统（按 IT 热负荷）", round(cooling_kw, 1), "kW", cool_price, "液冷CDU/冷板" if cooling == "liquid" else "精密空调"),
        _line("机房装修/土建摊销", round(area, 1), "㎡", _f(d0.get("fitout_cny_per_m2"))),
    ]

    def _sum(rows: list[dict[str, Any]]) -> float:
        return round(sum(r["amount"] for r in rows), 2)

    eq_sum = _sum(server) + _sum(network)
    fac_sum = _sum(facility)
    install = round(eq_sum * _f(d0.get("install_pct"), 3) / 100.0, 2)
    software = round(eq_sum * _f(d0.get("software_pct"), 2) / 100.0, 2)
    services = [
        _line("安装调试/集成", 1, "项", install, f"按设备费 {_f(d0.get('install_pct'))}%"),
        _line("集群软件/调度（估）", 1, "项", software, f"按设备费 {_f(d0.get('software_pct'))}%"),
    ]
    subtotal = eq_sum + fac_sum + _sum(services)
    contingency = round(subtotal * _f(d0.get("contingency_pct"), 5) / 100.0, 2)
    pretax = round(subtotal + contingency, 2)
    vat = round(pretax * _f(d0.get("vat_pct"), 13) / 100.0, 2)
    total = round(pretax + vat, 2)

    kwh_year = facility_kw * _f(d0.get("hours_per_year"), 8000)
    opex_year = round(kwh_year * _f(d0.get("electricity_cny_per_kwh"), 0.65), 2)

    return {
        "meta": {
            "project": req.get("project") or "未命名算力中心",
            "location": req.get("location") or "",
            "cooling": cooling,
            "gpu_name": gpu.get("name"),
            "price_note": catalog.get("note"),
        },
        "scale": {
            "mode": mode,
            "want_gpu": want_gpu,
            "gpu_buy": gpu_buy,
            "nodes": nodes,
            "cards_per_node": cards_per_node,
            "pflops_fp16": round(pflops, 3),
            "tflops_per_card": tflops,
            "it_kw": round(it_kw, 1),
            "facility_kw": round(facility_kw, 1),
            "pue": pue,
            "racks": racks,
            "area_m2": round(area, 1),
        },
        "sections": [
            {"title": "一、计算服务器", "rows": server, "subtotal": _sum(server)},
            {"title": "二、互联网络", "rows": network, "subtotal": _sum(network)},
            {"title": "三、机房配套", "rows": facility, "subtotal": fac_sum},
            {"title": "四、软件与服务", "rows": services, "subtotal": _sum(services)},
        ],
        "totals": {
            "equipment": eq_sum,
            "facility": fac_sum,
            "services": _sum(services),
            "contingency": contingency,
            "contingency_pct": _f(d0.get("contingency_pct")),
            "pretax": pretax,
            "vat": vat,
            "vat_pct": _f(d0.get("vat_pct")),
            "total": total,
            "per_gpu": round(total / gpu_buy, 2) if gpu_buy else 0,
            "per_pflops": round(total / pflops, 2) if pflops else 0,
            "opex_power_year": opex_year,
        },
        "gpu": {**gpu, "card_price_effective": round(card_price, 2), "node_price_effective": round(node_price, 2)},
        "prices": d0,
    }
