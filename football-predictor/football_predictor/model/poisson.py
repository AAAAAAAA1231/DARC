from __future__ import annotations

from math import exp, factorial, log
import numpy as np

from ..config import MAX_GOALS


def poisson_pmf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return exp(-lam) * (lam**k) / factorial(k)


def dixon_coles_tau(home_goals: int, away_goals: int, lam: float, mu: float, rho: float) -> float:
    if home_goals == 0 and away_goals == 0:
        return 1.0 - lam * mu * rho
    if home_goals == 0 and away_goals == 1:
        return 1.0 + lam * rho
    if home_goals == 1 and away_goals == 0:
        return 1.0 + mu * rho
    if home_goals == 1 and away_goals == 1:
        return 1.0 - rho
    return 1.0


def score_matrix(lam: float, mu: float, rho: float = -0.05, max_goals: int = MAX_GOALS) -> np.ndarray:
    lam = max(0.05, min(5.5, float(lam)))
    mu = max(0.05, min(5.5, float(mu)))
    mat = np.zeros((max_goals + 1, max_goals + 1), dtype=float)
    home_pmf = np.array([poisson_pmf(i, lam) for i in range(max_goals + 1)])
    away_pmf = np.array([poisson_pmf(j, mu) for j in range(max_goals + 1)])
    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            mat[i, j] = home_pmf[i] * away_pmf[j] * max(0.05, dixon_coles_tau(i, j, lam, mu, rho))
    total = mat.sum()
    if total <= 0:
        mat[0, 0] = 1.0
        return mat
    return mat / total


def matrix_1x2(mat: np.ndarray) -> tuple[float, float, float]:
    home = float(np.tril(mat, -1).sum())
    draw = float(np.trace(mat))
    away = float(np.triu(mat, 1).sum())
    s = home + draw + away
    if s <= 0:
        return 1 / 3, 1 / 3, 1 / 3
    return home / s, draw / s, away / s


def top_scores(mat: np.ndarray, n: int = 8) -> list[tuple[str, float]]:
    idx = np.dstack(np.unravel_index(np.argsort(mat.ravel())[::-1], mat.shape))[0]
    out = []
    for i, j in idx[:n]:
        out.append((f"{int(i)}-{int(j)}", float(mat[int(i), int(j)])))
    return out


def most_likely_score(mat: np.ndarray) -> str:
    i, j = np.unravel_index(int(np.argmax(mat)), mat.shape)
    return f"{int(i)}-{int(j)}"


def expected_goals(mat: np.ndarray) -> tuple[float, float]:
    goals = np.arange(mat.shape[0])
    xg_h = float((mat.sum(axis=1) * goals).sum())
    xg_a = float((mat.sum(axis=0) * goals).sum())
    return xg_h, xg_a


def log_loss_poisson(hg: int, ag: int, lam: float, mu: float, rho: float) -> float:
    p = poisson_pmf(hg, lam) * poisson_pmf(ag, mu) * max(1e-6, dixon_coles_tau(hg, ag, lam, mu, rho))
    return -log(max(p, 1e-12))


def rescale_matrix_to_1x2(mat: np.ndarray, p_home: float, p_draw: float, p_away: float) -> np.ndarray:
    """把比分矩阵的 1X2 边缘对齐到纠偏后的概率，保持条件比分形状。"""
    cur_h, cur_d, cur_a = matrix_1x2(mat)
    out = mat.copy()
    n = out.shape[0]
    for i in range(n):
        for j in range(n):
            if i > j:
                scale = p_home / max(cur_h, 1e-9)
            elif i == j:
                scale = p_draw / max(cur_d, 1e-9)
            else:
                scale = p_away / max(cur_a, 1e-9)
            out[i, j] *= scale
    s = out.sum()
    return out / s if s > 0 else mat
