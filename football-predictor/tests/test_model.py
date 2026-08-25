from datetime import datetime, timedelta

from football_predictor.names import canonical_name, display_cn, resolve_team
from football_predictor.model.poisson import matrix_1x2, most_likely_score, score_matrix
from football_predictor.model.dixon_coles import fit_dixon_coles
from football_predictor.model.elo import elo_1x2, fit_elo
from football_predictor.data.historical import Match
from football_predictor.model.adjustments import Adjustment, apply_multipliers, news_adjustments
from football_predictor.data.espn import NewsItem, american_to_prob
from football_predictor.model.calibrate import Calibration


def test_name_aliases_three_leagues():
    assert canonical_name("Ath Madrid") == "Atletico Madrid"
    assert display_cn("Barca") == "巴塞罗那"
    assert display_cn("Bayern") == "拜仁慕尼黑"
    assert canonical_name("Inter") == "Internazionale"
    assert canonical_name("M'gladbach") == "Borussia Monchengladbach"
    assert canonical_name("Espanol") == "Espanyol"
    assert canonical_name("La Coruna") == "Deportivo"
    assert resolve_team("勒沃库森") is not None


def test_score_matrix_normalized_and_home_favorite():
    mat = score_matrix(1.8, 0.9, rho=-0.05)
    assert abs(float(mat.sum()) - 1.0) < 1e-9
    ph, pd, pa = matrix_1x2(mat)
    assert ph > pa
    assert abs(ph + pd + pa - 1) < 1e-9
    assert most_likely_score(score_matrix(2.4, 0.4))[0] >= "1"


def test_dixon_coles_recovers_strength():
    base = datetime(2025, 8, 1)
    matches = []
    for i in range(40):
        matches.append(
            Match("laliga", base + timedelta(days=i), "Barcelona", "Getafe", 3, 0, division="SP1")
        )
        matches.append(
            Match("laliga", base + timedelta(days=i), "Getafe", "Barcelona", 0, 2, division="SP1")
        )
    model = fit_dixon_coles(matches, max_iter=25)
    lam, mu = model.expected_goals("Barcelona", "Getafe")
    assert lam > mu
    assert model.attack[model.teams.index("Barcelona")] > model.attack[model.teams.index("Getafe")]
    assert model.home_adv >= 1.08


def test_elo_home_advantage():
    ph, pd, pa = elo_1x2(1600, 1500)
    assert ph > pa
    assert abs(ph + pd + pa - 1) < 1e-9


def test_news_injury_keyword_adjusts_attack():
    news = [
        NewsItem(
            title="Barcelona striker ruled out with hamstring injury",
            summary="The forward is injured and will miss the La Liga clash",
            source="test",
        )
    ]
    adjs = news_adjustments(news, "Barcelona", "Getafe", ["Barcelona", "巴塞罗那"], ["Getafe", "赫塔费"])
    assert any(a.target == "home_att" and a.delta < 0 for a in adjs)


def test_apply_multipliers_caps_xg():
    adjs = [Adjustment("t", "home_att", 0.5, "too big")]
    lam, mu, draw, _ = apply_multipliers(1.2, 1.0, adjs)
    assert 0.15 <= lam <= 4.8
    assert mu == 1.0 or mu > 0


def test_calibration_shrinks_toward_empirical():
    cal = Calibration(bins=[(0.5, 0.62, 0.40)], brier=0.2, accuracy_1x2=0.5, n=80, note="x")
    h, d, a = cal.adjust(0.55, 0.25, 0.20)
    assert h < 0.55
    assert abs(h + d + a - 1) < 1e-9


def test_score_consistent_with_1x2():
    from football_predictor.model.poisson import most_likely_score_for_1x2, score_matrix

    mat = score_matrix(1.5, 1.3, rho=-0.08)
    score = most_likely_score_for_1x2(mat, "主胜")
    h, a = map(int, score.split("-"))
    assert h > a
    score_d = most_likely_score_for_1x2(mat, "平局")
    h, a = map(int, score_d.split("-"))
    assert h == a


def test_american_odds():
    assert abs(american_to_prob(-200) - 2 / 3) < 1e-6
    assert abs(american_to_prob(100) - 0.5) < 1e-6
    assert abs(american_to_prob("+180") - (100 / 280)) < 1e-6


def test_extract_espn_soccer_moneyline():
    from football_predictor.data.espn import _extract_moneyline

    odds = [
        {
            "drawOdds": {"moneyLine": 235},
            "moneyline": {
                "home": {"close": {"odds": "+180"}},
                "away": {"close": {"odds": "+155"}},
                "draw": {"close": {"odds": "+235"}},
            },
        }
    ]
    found = _extract_moneyline(odds)
    assert found is not None
    h, d, a = found
    assert abs(h + d + a - 1) < 1e-9
    assert 0.25 < h < 0.4
    assert a > h  # +155 比 +180 更被看好
