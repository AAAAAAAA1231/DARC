from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp, log
import numpy as np

from ..config import DC_MAX_ITER, HALF_LIFE_DAYS, MAX_GOALS
from ..data.historical import Match
from .poisson import dixon_coles_tau, poisson_pmf


@dataclass
class DixonColesModel:
    teams: list[str]
    attack: np.ndarray
    defense: np.ndarray
    home_adv: float
    rho: float
    fitted_at: str
    n_matches: int
    loglik: float

    def index(self, team: str) -> int | None:
        try:
            return self.teams.index(team)
        except ValueError:
            return None

    def expected_goals(self, home: str, away: str) -> tuple[float, float]:
        hi = self.index(home)
        ai = self.index(away)
        # 未知球队（升班马冷门）用联赛平均
        att_h = float(self.attack[hi]) if hi is not None else 1.0
        def_a = float(self.defense[ai]) if ai is not None else 1.0
        att_a = float(self.attack[ai]) if ai is not None else 1.0
        def_h = float(self.defense[hi]) if hi is not None else 1.0
        lam = max(0.15, att_h * def_a * self.home_adv)
        mu = max(0.15, att_a * def_h)
        return lam, mu


def _weights(dates: list[datetime], as_of: datetime, half_life: float) -> np.ndarray:
    w = np.zeros(len(dates), dtype=float)
    ln2 = log(2.0)
    for i, dt in enumerate(dates):
        days = max(0.0, (as_of - dt).total_seconds() / 86400.0)
        w[i] = exp(-ln2 * days / half_life)
    # 二级联赛权重在调用方已乘折扣；这里只做时间衰减
    s = w.sum()
    if s <= 0:
        return np.ones(len(dates)) / max(len(dates), 1)
    return w


def _weighted_ll(
    hg: np.ndarray,
    ag: np.ndarray,
    lam: np.ndarray,
    mu: np.ndarray,
    rho: float,
    w: np.ndarray,
) -> float:
    ll = 0.0
    for i in range(len(hg)):
        p = (
            poisson_pmf(int(hg[i]), float(lam[i]))
            * poisson_pmf(int(ag[i]), float(mu[i]))
            * max(1e-6, dixon_coles_tau(int(hg[i]), int(ag[i]), float(lam[i]), float(mu[i]), rho))
        )
        ll += float(w[i]) * log(max(p, 1e-12))
    return ll


def fit_dixon_coles(
    matches: list[Match],
    as_of: datetime | None = None,
    half_life: float = HALF_LIFE_DAYS,
    max_iter: int = DC_MAX_ITER,
    second_div_discount: float = 0.45,
    home_adv_prior: float = 1.32,
) -> DixonColesModel:
    if not matches:
        raise ValueError("没有可用于拟合的历史比赛")
    as_of = as_of or matches[-1].date
    teams = sorted({m.home for m in matches} | {m.away for m in matches})
    idx = {t: i for i, t in enumerate(teams)}
    n = len(teams)
    home_idx = np.array([idx[m.home] for m in matches], dtype=int)
    away_idx = np.array([idx[m.away] for m in matches], dtype=int)
    hg = np.array([m.home_goals for m in matches], dtype=float)
    ag = np.array([m.away_goals for m in matches], dtype=float)
    dates = [m.date for m in matches]
    w = _weights(dates, as_of, half_life)
    for i, m in enumerate(matches):
        if m.division.endswith("2"):
            w[i] *= second_div_discount

        attack = np.ones(n, dtype=float)
    defense = np.ones(n, dtype=float)
    home_adv = float(home_adv_prior)
    rho = -0.05

    for _ in range(max_iter):
        lam_div = defense[away_idx] * home_adv
        mu_div = defense[home_idx]
        # 攻击力：进球 / (对手防守 * 主场因子)
        num_att = np.zeros(n)
        den_att = np.zeros(n)
        np.add.at(num_att, home_idx, w * hg)
        np.add.at(den_att, home_idx, w * lam_div)
        np.add.at(num_att, away_idx, w * ag)
        np.add.at(den_att, away_idx, w * mu_div)
        attack = np.clip(num_att / np.maximum(den_att, 1e-6), 0.25, 3.2)
        attack /= attack.mean()

        lam_part = attack[home_idx] * home_adv
        mu_part = attack[away_idx]
        num_def = np.zeros(n)
        den_def = np.zeros(n)
        np.add.at(num_def, away_idx, w * hg)
        np.add.at(den_def, away_idx, w * lam_part)
        np.add.at(num_def, home_idx, w * ag)
        np.add.at(den_def, home_idx, w * mu_part)
        defense = np.clip(num_def / np.maximum(den_def, 1e-6), 0.25, 3.2)
        defense /= defense.mean()

        lam = attack[home_idx] * defense[away_idx]
        raw_home = float(np.sum(w * hg) / max(np.sum(w * lam), 1e-6))
        home_adv = float(np.clip(0.7 * raw_home + 0.3 * home_adv_prior, 1.08, 1.70))

    lam = attack[home_idx] * defense[away_idx] * home_adv
    mu = attack[away_idx] * defense[home_idx]
    best_rho, best_ll = rho, -1e18
    for cand in np.linspace(-0.18, 0.08, 14):
        ll = _weighted_ll(hg, ag, lam, mu, float(cand), w)
        if ll > best_ll:
            best_ll, best_rho = ll, float(cand)

    return DixonColesModel(
        teams=teams,
        attack=attack,
        defense=defense,
        home_adv=float(home_adv),
        rho=best_rho,
        fitted_at=as_of.isoformat(),
        n_matches=len(matches),
        loglik=best_ll,
    )


def predict_from_model(model: DixonColesModel, home: str, away: str) -> tuple[float, float]:
    return model.expected_goals(home, away)
