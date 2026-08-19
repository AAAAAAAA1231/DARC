from __future__ import annotations

import math
from typing import Any


def room_index(length: float, width: float, h_m: float) -> float:
    if h_m <= 0.2:
        h_m = 0.2
    return (length * width) / (h_m * (length + width))


def utilization_factor(k: float) -> float:
    k = max(0.4, min(5.0, k))
    table = [
        (0.4, 0.26), (0.6, 0.32), (0.8, 0.40), (1.0, 0.46), (1.25, 0.51),
        (1.5, 0.55), (2.0, 0.60), (3.0, 0.66), (4.0, 0.70), (5.0, 0.73),
    ]
    for i in range(1, len(table)):
        k0, u0 = table[i - 1]
        k1, u1 = table[i]
        if k <= k1:
            t = (k - k0) / (k1 - k0)
            return u0 + t * (u1 - u0)
    return table[-1][1]


def lamps_needed(E: float, area: float, flux: float, uf: float, mf: float) -> float:
    if flux * uf * mf <= 0:
        return 999
    return E * area / (flux * uf * mf)


def space_grid(length: float, width: float, h_m: float, shr: float) -> tuple[int, int, int]:
    max_s = max(0.6, shr * max(h_m, 0.8))
    nx = max(1, math.ceil(length / max_s - 1e-9))
    ny = max(1, math.ceil(width / max_s - 1e-9))
    return nx, ny, nx * ny


def grid_for_count(n: int, length: float, width: float, max_n: int | None = None) -> tuple[int, int, int]:
    n = max(1, int(n))
    max_n = max(n, int(max_n or n + 12))
    ratio = length / max(width, 0.1)
    best = None
    for nx in range(1, max_n + 4):
        ny = max(1, math.ceil(n / nx))
        total = nx * ny
        if total < n or total > max_n:
            continue
        score = abs(nx / ny - ratio) + 0.04 * (total - n)
        if best is None or score < best[0]:
            best = (score, nx, ny, total)
    if best is None:
        nx = max(1, round(math.sqrt(n * ratio)))
        ny = max(1, math.ceil(n / nx))
        return nx, ny, nx * ny
    return best[1], best[2], best[3]


def grid_counts(n: float, length: float, width: float, h_m: float, shr: float) -> tuple[int, int, int]:
    n_need = max(1, math.ceil(n - 1e-9))
    _sx, _sy, n_space = space_grid(length, width, h_m, shr)
    n_use = max(n_need, n_space)
    return grid_for_count(n_need, length, width, max_n=max(n_use, n_need))


def mount_height_m(room_height: float, work_h: float, kind: str, room_name: str) -> tuple[float, float, bool]:
    """Return (h_m, lamp AFF, used_suspended_ceiling). Office panels are not on a 6 m roof."""
    raw_aff = room_height
    tall = room_name in ("工业一般加工", "工业精细加工", "门厅/大堂", "商场营业厅", "车库/停车场")
    high_bay = kind == "工矿灯"
    if (not tall) and (not high_bay) and room_height > 3.3:
        raw_aff = 3.1
    h_m = max(0.5, raw_aff - work_h)
    return h_m, raw_aff, raw_aff + 0.05 < room_height


def fixture_points(length: float, width: float, nx: int, ny: int) -> list[tuple[float, float]]:
    pts = []
    for i in range(nx):
        for j in range(ny):
            pts.append(((i + 0.5) * length / nx, (j + 0.5) * width / ny))
    return pts


def avg_illuminance(n: int, flux: float, uf: float, mf: float, area: float) -> float:
    if area <= 0:
        return 0
    return n * flux * uf * mf / area


def emergency_points(length: float, width: float, kind: str) -> list[dict[str, Any]]:
    pts = [
        {"x": 0.3, "y": width / 2, "kind": "疏散标志"},
        {"x": length - 0.3, "y": width / 2, "kind": "疏散标志"},
    ]
    if kind in ("走廊", "楼梯", "门厅/大堂", "车库/停车场") or length * width >= 20:
        n = max(1, round(max(length, width) / 8))
        for i in range(n):
            pts.append({"x": (i + 0.5) * length / n, "y": 0.25, "kind": "应急照明"})
    return pts
