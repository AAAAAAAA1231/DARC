from __future__ import annotations

from dataclasses import dataclass
import re

from ..config import NEWS_ADJUST_CAP
from ..data.espn import Injury, NewsItem
from ..data.weather import Weather
from ..names import normalize_name


@dataclass
class Adjustment:
    factor: str
    target: str  # home_att / away_att / home_def / away_def / draw
    delta: float  # 乘性偏离，如 -0.08 表示 xG * 0.92
    reason: str


_INJURY_OUT = re.compile(
    r"(out|ruled out|injured|injury|hamstring|acl|knock|doubt|suspended|ban|red card|"
    r"伤停|停赛|缺阵|受伤|十字韧带|大腿|脚踝|红牌|禁赛|无法出战|报销)",
    re.I,
)
_KEY_POS = re.compile(r"(st|fw|cf|lw|rw|am|gk|striker|forward|goalkeeper|前锋|射手|门将|核心|队长)", re.I)
_MANAGER = re.compile(r"(sacked|fired|new manager|appointed|下课|换帅|新帅|主帅)", re.I)
_DERBY = re.compile(r"(derby|cl[aá]sico|rival|德比|国家德比|米兰德比|马德里德比)", re.I)
_MOTIVATION_UP = re.compile(r"(title race|top of|争冠|榜首|必须赢|生死战|保级)", re.I)
_MOTIVATION_DOWN = re.compile(r"(already relegated|dead rubber|rotation|rested|轮换|无欲无求|已保级|已降级)", re.I)
_WEATHER_BAD = re.compile(r"(storm|heavy rain|snow|暴雨|大风|暴雪)", re.I)


def _clip(delta: float) -> float:
    return max(-NEWS_ADJUST_CAP, min(NEWS_ADJUST_CAP, delta))


def _mentions(text: str, team_names: list[str]) -> bool:
    blob = normalize_name(text)
    return any(normalize_name(n) and normalize_name(n) in blob for n in team_names if n)


def injury_adjustments(
    injuries: list[Injury],
    home: str,
    away: str,
    home_names: list[str],
    away_names: list[str],
) -> list[Adjustment]:
    out: list[Adjustment] = []
    for inj in injuries:
        team = inj.team
        side = None
        if team == home or _mentions(team, home_names):
            side = "home"
        elif team == away or _mentions(team, away_names):
            side = "away"
        if not side:
            continue
        text = f"{inj.player} {inj.status} {inj.detail} {inj.position}"
        if not _INJURY_OUT.search(text) and inj.status:
            # ESPN 列表里出现即视为缺阵
            pass
        impact = -0.045
        if _KEY_POS.search(text):
            impact = -0.09
        if re.search(r"(gk|goalkeeper|门将)", text, re.I):
            # 门将缺阵主要打防守
            out.append(
                Adjustment(
                    "伤停",
                    f"{side}_def",
                    _clip(0.08),
                    f"{inj.player}（门将相关）状态：{inj.status or '缺阵'}",
                )
            )
            continue
        out.append(
            Adjustment(
                "伤停",
                f"{side}_att",
                _clip(impact),
                f"{inj.player} 伤停/出战成疑（{inj.status or '未标明'}）",
            )
        )
        out.append(
            Adjustment(
                "伤停",
                f"{side}_def",
                _clip(-impact * 0.4),
                f"{inj.player} 可能同时削弱防守结构",
            )
        )
    # 伤停人数过多额外惩罚
    home_n = sum(1 for a in out if a.target.startswith("home") and a.factor == "伤停")
    away_n = sum(1 for a in out if a.target.startswith("away") and a.factor == "伤停")
    if home_n >= 6:
        out.append(Adjustment("伤停规模", "home_att", -0.06, "主队伤停名单偏长，轮换深度承压"))
    if away_n >= 6:
        out.append(Adjustment("伤停规模", "away_att", -0.06, "客队伤停名单偏长，轮换深度承压"))
    return out


def news_adjustments(
    news: list[NewsItem],
    home: str,
    away: str,
    home_names: list[str],
    away_names: list[str],
) -> list[Adjustment]:
    out: list[Adjustment] = []
    seen_reasons: set[str] = set()
    for item in news:
        text = f"{item.title} {item.summary}"
        home_hit = _mentions(text, home_names + [home])
        away_hit = _mentions(text, away_names + [away])
        if _DERBY.search(text):
            reason = "德比/对抗情绪：进球方差上升、平局略增"
            if reason not in seen_reasons:
                out.append(Adjustment("赛事性质", "draw", 0.03, reason))
                seen_reasons.add(reason)
        if _MANAGER.search(text):
            side = "home" if home_hit and not away_hit else "away" if away_hit and not home_hit else None
            if side:
                reason = f"{'主' if side=='home' else '客'}队近期帅位变动，短期战意/战术不稳定"
                if reason not in seen_reasons:
                    out.append(Adjustment("帅位", f"{side}_att", 0.03, reason))
                    out.append(Adjustment("帅位", f"{side}_def", 0.04, reason))
                    seen_reasons.add(reason)
        if _INJURY_OUT.search(text):
            side = "home" if home_hit and not away_hit else "away" if away_hit and not home_hit else None
            if side:
                key_boost = -0.07 if _KEY_POS.search(text) else -0.035
                reason = f"舆情提到{'主' if side=='home' else '客'}队人员缺阵：{item.title[:48]}"
                if reason not in seen_reasons:
                    out.append(Adjustment("舆情伤停", f"{side}_att", _clip(key_boost), reason))
                    seen_reasons.add(reason)
        if _MOTIVATION_UP.search(text):
            side = "home" if home_hit and not away_hit else "away" if away_hit and not home_hit else None
            if side:
                reason = f"{'主' if side=='home' else '客'}队战意被媒体强调（争冠/保级/必须拿分）"
                if reason not in seen_reasons:
                    out.append(Adjustment("战意", f"{side}_att", 0.04, reason))
                    seen_reasons.add(reason)
        if _MOTIVATION_DOWN.search(text):
            side = "home" if home_hit and not away_hit else "away" if away_hit and not home_hit else None
            if side:
                reason = f"{'主' if side=='home' else '客'}队可能轮换或战意不足"
                if reason not in seen_reasons:
                    out.append(Adjustment("战意", f"{side}_att", -0.05, reason))
                    seen_reasons.add(reason)
        if _WEATHER_BAD.search(text):
            reason = "媒体提及极端天气，抑制进球"
            if reason not in seen_reasons:
                out.append(Adjustment("天气舆情", "home_att", -0.04, reason))
                out.append(Adjustment("天气舆情", "away_att", -0.04, reason))
                out.append(Adjustment("天气舆情", "draw", 0.02, reason))
                seen_reasons.add(reason)
    return out


def weather_adjustments(wx: Weather | None) -> list[Adjustment]:
    if not wx:
        return []
    out: list[Adjustment] = []
    rain = wx.precipitation_mm or 0.0
    wind = wx.wind_kmh or 0.0
    temp = wx.temperature_c
    if rain >= 1.5:
        mag = min(0.10, 0.03 + 0.02 * rain)
        out.append(Adjustment("现场天气", "home_att", -mag, f"降水 {rain:.1f}mm，地面湿滑，进球预期下调"))
        out.append(Adjustment("现场天气", "away_att", -mag, f"降水抑制客队推进"))
        out.append(Adjustment("现场天气", "draw", min(0.04, mag / 2), "恶劣天气增加平局"))
    if wind >= 35:
        out.append(Adjustment("现场天气", "home_att", -0.03, f"风速 {wind:.0f}km/h，传中/远射质量下降"))
        out.append(Adjustment("现场天气", "away_att", -0.03, "大风同样限制客队进攻"))
    if temp is not None and (temp <= 2 or temp >= 33):
        out.append(Adjustment("现场天气", "away_att", -0.03, f"气温 {temp:.0f}°C，客队适应成本更高"))
    return out


def form_adjustments(
    home_recent_gf: float,
    home_recent_ga: float,
    away_recent_gf: float,
    away_recent_ga: float,
    league_gf: float,
    n_home: int,
    n_away: int,
) -> list[Adjustment]:
    """赛季初小样本向联赛均值收缩。"""
    out: list[Adjustment] = []
    league_gf = max(league_gf, 0.8)

    def shrink(obs: float, n: int) -> float:
        w = n / (n + 6.0)
        return w * obs + (1 - w) * league_gf

    h_att = shrink(home_recent_gf, n_home) / league_gf
    a_att = shrink(away_recent_gf, n_away) / league_gf
    h_def = shrink(home_recent_ga, n_home) / league_gf
    a_def = shrink(away_recent_ga, n_away) / league_gf
    # 转成温和乘数偏离
    if abs(h_att - 1) > 0.04:
        out.append(Adjustment("近期状态", "home_att", _clip((h_att - 1) * 0.35), f"主队近况攻击指数 {h_att:.2f}"))
    if abs(a_att - 1) > 0.04:
        out.append(Adjustment("近期状态", "away_att", _clip((a_att - 1) * 0.35), f"客队近况攻击指数 {a_att:.2f}"))
    if abs(h_def - 1) > 0.04:
        out.append(Adjustment("近期状态", "home_def", _clip((h_def - 1) * 0.30), f"主队近况失球指数 {h_def:.2f}"))
    if abs(a_def - 1) > 0.04:
        out.append(Adjustment("近期状态", "away_def", _clip((a_def - 1) * 0.30), f"客队近况失球指数 {a_def:.2f}"))
    return out


def apply_multipliers(
    lam: float,
    mu: float,
    adjustments: list[Adjustment],
) -> tuple[float, float, float, list[Adjustment]]:
    """返回调整后 λ、μ 以及平局加项。"""
    home_att = 1.0
    away_att = 1.0
    home_def = 1.0  # >1 表示更容易丢球
    away_def = 1.0
    draw_add = 0.0
    for adj in adjustments:
        if adj.target == "home_att":
            home_att *= 1.0 + adj.delta
        elif adj.target == "away_att":
            away_att *= 1.0 + adj.delta
        elif adj.target == "home_def":
            home_def *= 1.0 + adj.delta
        elif adj.target == "away_def":
            away_def *= 1.0 + adj.delta
        elif adj.target == "draw":
            draw_add += adj.delta
    # 主队进球受主攻和客防影响
    new_lam = lam * home_att * away_def
    new_mu = mu * away_att * home_def
    new_lam = float(max(0.15, min(4.8, new_lam)))
    new_mu = float(max(0.15, min(4.8, new_mu)))
    draw_add = float(max(-0.08, min(0.08, draw_add)))
    return new_lam, new_mu, draw_add, adjustments
