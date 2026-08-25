from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Callable

from ..config import BLEND_DC, BLEND_ELO, BLEND_MARKET, LEAGUES, LEAGUE_ORDER, League
from ..data.espn import Fixture, Injury, NewsItem, list_fixtures, list_injuries, list_news, list_teams
from ..data.historical import Match, load_league_history
from ..data.news import collect_match_news
from ..data.weather import Weather, fetch_weather
from ..names import canonical_name, display_cn, stadium_coords, team_keywords
from .adjustments import (
    Adjustment,
    apply_multipliers,
    form_adjustments,
    injury_adjustments,
    news_adjustments,
    weather_adjustments,
)
from .calibrate import Calibration, calibrate_from_holdout, split_holdout
from .dixon_coles import DixonColesModel, fit_dixon_coles
from .elo import EloTable, elo_1x2, fit_elo
from .poisson import (
    expected_goals,
    matrix_1x2,
    most_likely_score_for_1x2,
    rescale_matrix_to_1x2,
    score_matrix,
    top_scores,
)

ProgressCb = Callable[[str], None]


@dataclass
class LeagueEngine:
    league: League
    matches: list[Match]
    model: DixonColesModel
    elo: EloTable
    calibration: Calibration
    teams: list[str]


@dataclass
class PredictionResult:
    league_key: str
    league_cn: str
    home: str
    away: str
    home_cn: str
    away_cn: str
    kickoff: str
    venue: str
    p_home: float
    p_draw: float
    p_away: float
    pred_1x2_90: str
    pred_score_90: str
    final_1x2: str
    final_score: str
    final_note: str
    xg_home: float
    xg_away: float
    top_scores: list[tuple[str, float]]
    confidence: float
    historical_accuracy: float
    factors: list[str]
    adjustments: list[Adjustment]
    news: list[NewsItem]
    injuries: list[Injury]
    weather: str
    market: tuple[float, float, float] | None
    calibration_note: str
    steps: list[str] = field(default_factory=list)


def _blend(parts: list[tuple[float, tuple[float, float, float]]]) -> tuple[float, float, float]:
    wsum = sum(w for w, _ in parts if w > 0)
    if wsum <= 0:
        return 1 / 3, 1 / 3, 1 / 3
    h = d = a = 0.0
    for w, (ph, pd, pa) in parts:
        if w <= 0:
            continue
        h += w * ph
        d += w * pd
        a += w * pa
    s = h + d + a
    return h / s, d / s, a / s


def _label_1x2(ph: float, pd: float, pa: float) -> str:
    best = max(("主胜", ph), ("平局", pd), ("客胜", pa), key=lambda t: t[1])
    return best[0]


def _recent_stats(matches: list[Match], team: str, as_of: datetime, n: int = 8) -> tuple[float, float, int]:
    recent = [m for m in matches if m.date < as_of and (m.home == team or m.away == team)]
    recent = recent[-n:]
    if not recent:
        return 1.2, 1.2, 0
    gf = ga = 0.0
    for m in recent:
        if m.home == team:
            gf += m.home_goals
            ga += m.away_goals
        else:
            gf += m.away_goals
            ga += m.home_goals
    k = len(recent)
    return gf / k, ga / k, k


def _league_avg_goals(matches: list[Match]) -> float:
    top = [m for m in matches if not m.division.endswith("2")][-380:]
    if not top:
        return 1.25
    return sum(m.home_goals + m.away_goals for m in top) / (2 * len(top))


class Predictor:
    def __init__(self) -> None:
        self.engines: dict[str, LeagueEngine] = {}

    def ready(self) -> bool:
        return len(self.engines) == len(LEAGUES)

    def build(self, progress: ProgressCb | None = None) -> None:
        cb = progress or (lambda _: None)
        for key in LEAGUE_ORDER:
            league = LEAGUES[key]
            cb(f"正在下载 {league.name_cn} 历史赛果（含升班马二级联赛）…")
            matches = load_league_history(league)
            if len(matches) < 80:
                raise RuntimeError(f"{league.name_cn} 历史数据不足（{len(matches)} 场）")
            train, holdout = split_holdout(matches)
            cb(f"正在拟合 {league.name_cn} 校准用模型（{len(train)} 场）…")
            model_cv = fit_dixon_coles(train, home_adv_prior=league.typical_home_adv)
            cb(f"正在用最近 {len(holdout)} 场做概率校准…")
            calibration = calibrate_from_holdout(model_cv, holdout)
            cb(f"正在全量重拟合 {league.name_cn} Dixon-Coles / Elo（{len(matches)} 场）…")
            model = fit_dixon_coles(matches, home_adv_prior=league.typical_home_adv)
            elo = fit_elo(matches)
            try:
                live_teams = list_teams(league)
            except Exception:
                live_teams = []
            teams = sorted(set(live_teams) | {m.home for m in matches[-400:]} | {m.away for m in matches[-400:]})
            self.engines[key] = LeagueEngine(
                league=league,
                matches=matches,
                model=model,
                elo=elo,
                calibration=calibration,
                teams=teams,
            )
            cb(
                f"{league.name_cn} 就绪：历史 {len(matches)} 场，"
                f"校准命中率 {calibration.accuracy_1x2:.1%}"
            )

    def upcoming(self, league_key: str | None = None, days: int = 12) -> list[Fixture]:
        now = datetime.now(timezone.utc)
        start = (now - timedelta(days=1)).strftime("%Y%m%d")
        end = (now + timedelta(days=days)).strftime("%Y%m%d")
        keys = [league_key] if league_key else LEAGUE_ORDER
        out: list[Fixture] = []
        for key in keys:
            league = LEAGUES[key]
            try:
                out.extend(list_fixtures(league, start, end))
            except Exception:
                continue
        out.sort(key=lambda f: (f.league, f.date))
        return out

    def upcoming_unplayed(self, days: int = 8, max_per_league: int = 6) -> list[Fixture]:
        out: list[Fixture] = []
        for key in LEAGUE_ORDER:
            live = [fx for fx in self.upcoming(key, days=days) if fx.status != "post"]
            out.extend(live[:max_per_league])
        out.sort(key=lambda f: (f.date, f.league))
        return out

    def predict_all_upcoming(self, progress: ProgressCb | None = None) -> list[PredictionResult]:
        cb = progress or (lambda _: None)
        fixtures = self.upcoming_unplayed()
        if not fixtures:
            return []
        results: list[PredictionResult] = []
        total = len(fixtures)
        for i, fx in enumerate(fixtures, 1):
            cb(f"正在联网预测 {i}/{total}  {LEAGUES[fx.league].name_cn}  {fx.home_cn} vs {fx.away_cn}")
            try:
                results.append(self.predict_fixture(fx, light=True))
            except Exception as exc:
                cb(f"{fx.home_cn} vs {fx.away_cn} 失败：{exc}")
        return results

    def predict_fixture(self, fixture: Fixture, progress: ProgressCb | None = None, light: bool = False) -> PredictionResult:
        return self.predict(
            fixture.league,
            fixture.home,
            fixture.away,
            kickoff=fixture.date,
            venue=fixture.venue,
            market=fixture.market,
            home_form=fixture.home_form,
            away_form=fixture.away_form,
            progress=progress,
            light=light,
        )

    def _attach_live_fixture(
        self,
        league_key: str,
        home: str,
        away: str,
        kickoff: datetime | None,
        venue: str,
        market: tuple[float, float, float] | None,
        home_form: str,
        away_form: str,
    ):
        try:
            fixtures = self.upcoming(league_key)
        except Exception:
            return kickoff, venue, market, home_form, away_form
        for fx in fixtures:
            if fx.home == home and fx.away == away:
                return (
                    fx.date if kickoff is None else kickoff,
                    venue or fx.venue,
                    market or fx.market,
                    home_form or fx.home_form,
                    away_form or fx.away_form,
                )
        return kickoff, venue, market, home_form, away_form

    def predict(
        self,
        league_key: str,
        home: str,
        away: str,
        kickoff: datetime | None = None,
        venue: str = "",
        market: tuple[float, float, float] | None = None,
        home_form: str = "",
        away_form: str = "",
        progress: ProgressCb | None = None,
        light: bool = False,
    ) -> PredictionResult:
        if league_key not in self.engines:
            raise RuntimeError("模型尚未训练，请先加载数据")
        cb = progress or (lambda _: None)
        eng = self.engines[league_key]
        home = canonical_name(home)
        away = canonical_name(away)
        if kickoff is None or market is None:
            kickoff, venue, market, home_form, away_form = self._attach_live_fixture(
                league_key, home, away, kickoff, venue, market, home_form, away_form
            )
        kickoff = kickoff or datetime.now(timezone.utc)
        if kickoff.tzinfo is None:
            kickoff = kickoff.replace(tzinfo=timezone.utc)
        steps: list[str] = []

        cb("计算基础攻防期望进球…")
        lam0, mu0 = eng.model.expected_goals(home, away)
        steps.append(
            f"Dixon-Coles 基础期望：主 {lam0:.2f} / 客 {mu0:.2f}，"
            f"联赛主场因子 {eng.model.home_adv:.2f}，ρ={eng.model.rho:.3f}"
        )

        as_of = kickoff.replace(tzinfo=None)
        h_gf, h_ga, n_h = _recent_stats(eng.matches, home, as_of)
        a_gf, a_ga, n_a = _recent_stats(eng.matches, away, as_of)
        lg_avg = _league_avg_goals(eng.matches)
        adjs: list[Adjustment] = []
        adjs.extend(form_adjustments(h_gf, h_ga, a_gf, a_ga, lg_avg, n_h, n_a))
        if home_form:
            steps.append(f"ESPN 主队近况编码：{home_form}")
        if away_form:
            steps.append(f"ESPN 客队近况编码：{away_form}")

        cb("拉取伤停名单与联盟新闻…")
        injuries: list[Injury] = []
        espn_news: list[NewsItem] = []
        try:
            injuries = list_injuries(eng.league)
        except Exception as exc:
            steps.append(f"伤停接口暂不可用：{exc}")
        try:
            espn_news = list_news(eng.league)
        except Exception:
            espn_news = []

        home_names = team_keywords(home)
        away_names = team_keywords(away)
        team_inj = [i for i in injuries if i.team in (home, away)]
        adjs.extend(injury_adjustments(team_inj, home, away, home_names, away_names))

        cb("检索赛前网络舆情（伤停/帅位/战意/天气）…")
        web_news = collect_match_news(
            display_cn(home), display_cn(away), home, away, eng.league.name_cn, light=light
        )
        news = _merge_news(espn_news, web_news, home_names, away_names)
        adjs.extend(news_adjustments(news, home, away, home_names, away_names))

        wx: Weather | None = None
        coords = stadium_coords(home)
        if coords:
            cb("读取主场实时天气…")
            try:
                wx = fetch_weather(coords[0], coords[1])
            except Exception:
                wx = None
            if not venue:
                venue = coords[2]
        adjs.extend(weather_adjustments(wx))

        lam, mu, draw_add, adjs = apply_multipliers(lam0, mu0, adjs)
        steps.append(f"情报/状态纠偏后期望进球：主 {lam:.2f} / 客 {mu:.2f}")

        mat = score_matrix(lam, mu, eng.model.rho)
        p_dc = matrix_1x2(mat)
        # 联赛风格平局微调 + 情报平局加项
        ph, pd, pa = p_dc
        pd = max(0.08, pd + eng.league.draw_bias + draw_add)
        s = ph + pd + pa
        p_dc = (ph / s, pd / s, pa / s)

        p_elo = elo_1x2(eng.elo.get(home), eng.elo.get(away))
        steps.append(
            f"Elo：主 {eng.elo.get(home):.0f} vs 客 {eng.elo.get(away):.0f} → "
            f"主胜 {p_elo[0]:.1%} / 平 {p_elo[1]:.1%} / 客胜 {p_elo[2]:.1%}"
        )

        parts = [(BLEND_DC, p_dc), (BLEND_ELO, p_elo)]
        if market:
            parts.append((BLEND_MARKET, market))
            steps.append(
                f"市场隐含概率纠偏：主胜 {market[0]:.1%} / 平 {market[1]:.1%} / 客胜 {market[2]:.1%}"
            )
        else:
            steps.append("本场暂无可用市场赔率，完全走模型+情报。")

        blended = _blend(parts)
        cal_h, cal_d, cal_a = eng.calibration.adjust(*blended)
        steps.append(eng.calibration.note)
        mat = rescale_matrix_to_1x2(mat, cal_h, cal_d, cal_a)
        xg_h, xg_a = expected_goals(mat)
        tops = top_scores(mat, 8)
        label90 = _label_1x2(cal_h, cal_d, cal_a)
        score90 = most_likely_score_for_1x2(mat, label90)

        # 联赛无加时点球，最终结果 = 90 分钟（含补时）赛果
        final_note = (
            "三大联赛常规赛没有加时与点球；"
            "「最终结果」等于 90 分钟（含伤停补时）赛果。"
            "胜平负取 1X2 最大后验，比分取该结论下最可能的精确比分。"
        )
        entropy = -(
            cal_h * _safe_log(cal_h) + cal_d * _safe_log(cal_d) + cal_a * _safe_log(cal_a)
        )
        # 越确定熵越低；再结合历史命中率与情报完整度
        certainty = max(0.0, min(1.0, 1.0 - entropy / 1.0986))
        info_score = 0.55
        if team_inj:
            info_score += 0.08
        if news:
            info_score += 0.08
        if wx:
            info_score += 0.05
        if market:
            info_score += 0.08
        if n_h + n_a >= 8:
            info_score += 0.06
        confidence = max(0.38, min(0.91, 0.35 * certainty + 0.40 * eng.calibration.accuracy_1x2 + 0.25 * min(info_score, 1)))

        factors = [
            f"历史攻防（时间衰减 Dixon-Coles，半衰期 {160:.0f} 天）",
            f"主场优势：λ 乘子 {eng.model.home_adv:.2f}（{eng.league.name_cn} 拟合值）",
            f"Elo 实力差：{eng.elo.get(home) - eng.elo.get(away):+.0f}",
            f"近期样本：主队 {n_h} 场、客队 {n_a} 场",
            f"网络情报条目 {len(news)} 条，伤停 {len(team_inj)} 条",
            f"天气：{wx.summary if wx else '未获取'}",
        ]
        for adj in adjs[:12]:
            factors.append(f"{adj.factor} → {adj.reason}")

        kickoff_local = kickoff.astimezone().strftime("%Y-%m-%d %H:%M")
        cb("生成最终预测报告…")
        return PredictionResult(
            league_key=league_key,
            league_cn=eng.league.name_cn,
            home=home,
            away=away,
            home_cn=display_cn(home),
            away_cn=display_cn(away),
            kickoff=kickoff_local,
            venue=venue or (coords[2] if coords else ""),
            p_home=cal_h,
            p_draw=cal_d,
            p_away=cal_a,
            pred_1x2_90=label90,
            pred_score_90=score90,
            final_1x2=label90,
            final_score=score90,
            final_note=final_note,
            xg_home=xg_h,
            xg_away=xg_a,
            top_scores=tops,
            confidence=confidence,
            historical_accuracy=eng.calibration.accuracy_1x2,
            factors=factors,
            adjustments=adjs,
            news=news[:12],
            injuries=team_inj[:12],
            weather=wx.summary if wx else "无",
            market=market,
            calibration_note=eng.calibration.note,
            steps=steps,
        )


def _safe_log(p: float) -> float:
    from math import log

    return log(max(p, 1e-12))


def _merge_news(
    espn: list[NewsItem],
    web: list[NewsItem],
    home_names: list[str],
    away_names: list[str],
) -> list[NewsItem]:
    from ..names import normalize_name
    import re

    home_keys = [normalize_name(n) for n in home_names if n]
    away_keys = [normalize_name(n) for n in away_names if n]
    all_keys = [k for k in home_keys + away_keys if k]
    out: list[NewsItem] = []
    seen: set[str] = set()
    vs_pat = re.compile(r"\bvs\.?\b|对阵|VS|v\.", re.I)
    spam = re.compile(
        r"10bet|1xbet|博彩|充值|黄歰|银河游戏|womenofchina|彩票|外围|投注站",
        re.I,
    )
    for item in web + espn:
        title_key = item.title.strip().lower()
        if title_key in seen or not item.title:
            continue
        if spam.search(item.title) or spam.search(item.summary or ""):
            continue
        blob = normalize_name(f"{item.title} {item.summary}")
        if all_keys and not any(k in blob for k in all_keys):
            continue
        home_hit = any(k and k in blob for k in home_keys)
        away_hit = any(k and k in blob for k in away_keys)
        if vs_pat.search(item.title) and not (home_hit and away_hit):
            # 该队打其他对手的旧闻/前瞻，丢掉
            continue
        seen.add(title_key)
        out.append(item)
    return out
