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
        (0.6, 0.32), (0.8, 0.40), (1.0, 0.46), (1.25, 0.51),
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


def grid_counts(n: float, length: float, width: float, h_m: float, shr: float) -> tuple[int, int, int]:
    n = max(1, math.ceil(n - 1e-9))
    max_s = max(0.6, shr * max(h_m, 0.8))
    nx_max = max(1, math.ceil(length / max_s))
    ny_max = max(1, math.ceil(width / max_s))
    n_min_space = nx_max * ny_max
    n_use = max(n, n_min_space)
    ratio = length / max(width, 0.1)
    best = None
    for nx in range(1, n_use + 6):
        ny = max(1, math.ceil(n_use / nx))
        if nx * ny < n:
            continue
        s_x = length / nx
        s_y = width / ny
        score = abs(nx / ny - ratio) + 0.02 * (nx * ny - n) + (0.5 if s_x > max_s + 0.05 or s_y > max_s + 0.05 else 0)
        if best is None or score < best[0]:
            best = (score, nx, ny, nx * ny)
    assert best is not None
    return best[1], best[2], best[3]


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
    if kind in ("走廊", "楼梯", "门厅/大堂", "车库/停车场") or length * width >= 60:
        n = max(1, round(length / 10))
        for i in range(n):
            pts.append({"x": (i + 0.5) * length / n, "y": 0.25, "kind": "应急照明"})
    return pts
