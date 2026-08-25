from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..config import CALIBRATION_HOLDOUT
from ..data.historical import Match
from .dixon_coles import DixonColesModel
from .poisson import matrix_1x2, score_matrix


@dataclass
class Calibration:
    bins: list[tuple[float, float, float]]  # (pred_low, pred_high, observed)
    brier: float
    accuracy_1x2: float
    n: int
    note: str

    def adjust(self, p_home: float, p_draw: float, p_away: float) -> tuple[float, float, float]:
        if self.n < 20 or not self.bins:
            return p_home, p_draw, p_away
        # 对主胜概率做分箱收缩，再按比例分配剩余给平/客
        obs = None
        for lo, hi, empirical in self.bins:
            if lo <= p_home < hi:
                obs = empirical
                break
        if obs is None:
            return p_home, p_draw, p_away
        # 向经验频率收缩，样本量越大权重越高
        shrink = min(0.45, 0.12 + 0.002 * self.n)
        new_h = (1 - shrink) * p_home + shrink * obs
        rest = max(1e-6, 1.0 - new_h)
        old_rest = max(1e-6, 1.0 - p_home)
        new_d = p_draw / old_rest * rest
        new_a = p_away / old_rest * rest
        s = new_h + new_d + new_a
        return new_h / s, new_d / s, new_a / s


def _bin_edges() -> list[tuple[float, float]]:
    edges = [0.0, 0.22, 0.32, 0.42, 0.52, 0.62, 0.75, 1.01]
    return list(zip(edges[:-1], edges[1:]))


def calibrate_from_holdout(model: DixonColesModel, holdout: list[Match]) -> Calibration:
    if not holdout:
        return Calibration(bins=[], brier=0.25, accuracy_1x2=0.0, n=0, note="样本不足，未做历史校准")
    preds_h: list[float] = []
    actual_h: list[int] = []
    correct = 0
    brier_acc = 0.0
    for m in holdout:
        lam, mu = model.expected_goals(m.home, m.away)
        mat = score_matrix(lam, mu, model.rho)
        ph, pd, pa = matrix_1x2(mat)
        y = [1.0 if m.result == "H" else 0.0, 1.0 if m.result == "D" else 0.0, 1.0 if m.result == "A" else 0.0]
        brier_acc += ((ph - y[0]) ** 2 + (pd - y[1]) ** 2 + (pa - y[2]) ** 2) / 3.0
        pred = max(("H", ph), ("D", pd), ("A", pa), key=lambda t: t[1])[0]
        if pred == m.result:
            correct += 1
        preds_h.append(ph)
        actual_h.append(1 if m.result == "H" else 0)

    bins: list[tuple[float, float, float]] = []
    arr_p = np.array(preds_h)
    arr_y = np.array(actual_h)
    for lo, hi in _bin_edges():
        mask = (arr_p >= lo) & (arr_p < hi)
        if mask.sum() >= 4:
            bins.append((lo, hi, float(arr_y[mask].mean())))
        else:
            bins.append((lo, hi, (lo + hi) / 2))
    n = len(holdout)
    brier = brier_acc / max(n, 1)
    acc = correct / max(n, 1)
    note = (
        f"用最近 {n} 场历史赛果做概率校准："
        f"1X2 命中率 {acc:.1%}，Brier={brier:.3f}（越低越好）。"
    )
    return Calibration(bins=bins, brier=brier, accuracy_1x2=acc, n=n, note=note)


def split_holdout(matches: list[Match], n: int = CALIBRATION_HOLDOUT) -> tuple[list[Match], list[Match]]:
    top = [m for m in matches if not m.division.endswith("2")]
    if len(top) <= n + 80:
        return matches, top[-min(40, len(top)) :]
    return top[:-n], top[-n:]
