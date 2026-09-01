from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from math import exp

from ..config import ELO_HOME_ADV, ELO_K, ELO_MEAN
from ..data.historical import Match


def expected_score(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10 ** ((elo_b - elo_a) / 400.0))


def result_score(home_goals: int, away_goals: int) -> float:
    if home_goals > away_goals:
        return 1.0
    if home_goals < away_goals:
        return 0.0
    return 0.5


@dataclass
class EloTable:
    ratings: dict[str, float]
    n_matches: int

    def get(self, team: str) -> float:
        return self.ratings.get(team, ELO_MEAN)


def fit_elo(matches: list[Match], k: float = ELO_K, home_adv: float = ELO_HOME_ADV) -> EloTable:
    ratings: dict[str, float] = {}
    count = 0
    for m in matches:
        if m.division.endswith("2"):
            # 二级联赛对顶级 Elo 只做弱更新
            step = k * 0.35
        else:
            step = k
        rh = ratings.get(m.home, ELO_MEAN)
        ra = ratings.get(m.away, ELO_MEAN)
        exp_h = expected_score(rh + home_adv, ra)
        actual = result_score(m.home_goals, m.away_goals)
        # 大比分多更新一点
        goal_diff = abs(m.home_goals - m.away_goals)
        g = 1.0 if goal_diff <= 1 else 1.0 + 0.15 * (goal_diff - 1)
        delta = step * g * (actual - exp_h)
        ratings[m.home] = rh + delta
        ratings[m.away] = ra - delta
        count += 1
    return EloTable(ratings=ratings, n_matches=count)


def elo_1x2(home_elo: float, away_elo: float, home_adv: float = ELO_HOME_ADV) -> tuple[float, float, float]:
    """用 Elo 差估计 1X2。平局概率随实力差缩小而上升。"""
    diff = home_elo + home_adv - away_elo
    p_home_or_draw = 1.0 / (1.0 + 10 ** (-diff / 400.0))
    # 经验：平局基础约 0.26，实力越接近越高
    closeness = exp(-((diff / 180.0) ** 2))
    p_draw = 0.18 + 0.16 * closeness
    p_home = max(0.04, p_home_or_draw - p_draw / 2)
    p_away = max(0.04, 1.0 - p_home - p_draw)
    s = p_home + p_draw + p_away
    return p_home / s, p_draw / s, p_away / s
