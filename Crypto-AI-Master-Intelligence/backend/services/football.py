"""Football ensemble: Poisson + Elo + Monte Carlo. Injuries stay UNKNOWN without a provider."""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from typing import Any

import numpy as np
from scipy.stats import poisson
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sqlalchemy.orm import Session

from backend.core.enums import ModuleName
from backend.core.logging import get_logger
from backend.core.parsing import parse_timestamp, utcnow
from backend.data_sources.football import THESPORTSDB_LEAGUES, TheSportsDbProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import FootballBet, FootballMatch, FootballPrediction, PredictionRecord
from backend.services.model_center import ensure_default_version

logger = get_logger("football")


def _elo_update(rating: dict[str, float], home: str, away: str, hg: int, ag: int, k: float = 20.0) -> None:
    rh = rating.setdefault(home, 1500.0)
    ra = rating.setdefault(away, 1500.0)
    exp_h = 1 / (1 + 10 ** ((ra - (rh + 60)) / 400))
    if hg > ag:
        score = 1.0
    elif hg == ag:
        score = 0.5
    else:
        score = 0.0
    rating[home] = rh + k * (score - exp_h)
    rating[away] = ra + k * ((1 - score) - (1 - exp_h))


def _team_stats(history: list[dict[str, Any]]) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    rating: dict[str, float] = {}
    stats: dict[str, dict[str, float]] = defaultdict(lambda: {"gf": 0.0, "ga": 0.0, "n": 0.0, "home_gf": 0.0, "home_n": 0.0, "away_gf": 0.0, "away_n": 0.0})
    for match in history:
        hg, ag = match.get("home_goals"), match.get("away_goals")
        if hg is None or ag is None:
            continue
        home, away = match["home"], match["away"]
        _elo_update(rating, home, away, int(hg), int(ag))
        stats[home]["gf"] += hg
        stats[home]["ga"] += ag
        stats[home]["n"] += 1
        stats[home]["home_gf"] += hg
        stats[home]["home_n"] += 1
        stats[away]["gf"] += ag
        stats[away]["ga"] += hg
        stats[away]["n"] += 1
        stats[away]["away_gf"] += ag
        stats[away]["away_n"] += 1
    return rating, stats


def _features(home: str, away: str, rating: dict[str, float], stats: dict[str, dict[str, float]]) -> list[float]:
    h = stats.get(home, {"gf": 1.2, "ga": 1.2, "n": 1, "home_gf": 1.3, "home_n": 1, "away_gf": 1.1, "away_n": 1})
    a = stats.get(away, {"gf": 1.2, "ga": 1.2, "n": 1, "home_gf": 1.3, "home_n": 1, "away_gf": 1.1, "away_n": 1})
    return [
        rating.get(home, 1500.0) - rating.get(away, 1500.0),
        h["gf"] / max(h["n"], 1),
        h["ga"] / max(h["n"], 1),
        a["gf"] / max(a["n"], 1),
        a["ga"] / max(a["n"], 1),
        h["home_gf"] / max(h["home_n"], 1),
        a["away_gf"] / max(a["away_n"], 1),
    ]


def fit_tree_ensemble(history: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Walk-forward labels: features at time t use only matches strictly before t."""
    ordered = [m for m in history if m.get("home_goals") is not None and m.get("away_goals") is not None]
    if len(ordered) < 40:
        return None
    rating: dict[str, float] = {}
    stats: dict[str, dict[str, float]] = defaultdict(
        lambda: {"gf": 0.0, "ga": 0.0, "n": 0.0, "home_gf": 0.0, "home_n": 0.0, "away_gf": 0.0, "away_n": 0.0}
    )
    X: list[list[float]] = []
    y: list[int] = []
    for match in ordered:
        X.append(_features(match["home"], match["away"], rating, stats))
        hg, ag = int(match["home_goals"]), int(match["away_goals"])
        y.append(0 if hg > ag else 1 if hg == ag else 2)
        _elo_update(rating, match["home"], match["away"], hg, ag)
        stats[match["home"]]["gf"] += hg
        stats[match["home"]]["ga"] += ag
        stats[match["home"]]["n"] += 1
        stats[match["home"]]["home_gf"] += hg
        stats[match["home"]]["home_n"] += 1
        stats[match["away"]]["gf"] += ag
        stats[match["away"]]["ga"] += hg
        stats[match["away"]]["n"] += 1
        stats[match["away"]]["away_gf"] += ag
        stats[match["away"]]["away_n"] += 1
    rf = RandomForestClassifier(n_estimators=80, max_depth=4, random_state=7)
    gb = GradientBoostingClassifier(n_estimators=60, max_depth=2, random_state=7)
    rf.fit(X, y)
    gb.fit(X, y)
    return {"rf": rf, "gb": gb}


def tree_probs(bundle: dict[str, Any] | None, home: str, away: str, rating: dict[str, float], stats: dict[str, dict[str, float]]) -> list[float] | None:
    if not bundle:
        return None
    x = np.array([_features(home, away, rating, stats)])

    def _expand(model) -> np.ndarray:
        proba = model.predict_proba(x)[0]
        full = np.zeros(3)
        for cls, prob in zip(model.classes_, proba, strict=False):
            full[int(cls)] = float(prob)
        return full

    full = 0.5 * _expand(bundle["rf"]) + 0.5 * _expand(bundle["gb"])
    s = full.sum() or 1.0
    return [float(full[0] / s), float(full[1] / s), float(full[2] / s)]


def predict_match(
    home: str,
    away: str,
    rating: dict[str, float],
    stats: dict[str, dict[str, float]],
    rng: np.random.Generator,
    tree_bundle: dict[str, Any] | None = None,
) -> dict[str, Any]:
    h = stats.get(home, {"gf": 1.2, "ga": 1.2, "n": 1, "home_gf": 1.3, "home_n": 1})
    a = stats.get(away, {"gf": 1.2, "ga": 1.2, "n": 1, "away_gf": 1.1, "away_n": 1})
    league_avg = 1.3
    att_h = (h["gf"] / max(h["n"], 1)) / league_avg
    att_a = (a["gf"] / max(a["n"], 1)) / league_avg
    def_h = (h["ga"] / max(h["n"], 1)) / league_avg
    def_a = (a["ga"] / max(a["n"], 1)) / league_avg
    lam_h = max(0.2, league_avg * att_h * def_a * 1.1)
    lam_a = max(0.2, league_avg * att_a * def_h * 0.95)
    elo_h = rating.get(home, 1500.0)
    elo_a = rating.get(away, 1500.0)
    elo_adj = (elo_h - elo_a) / 400.0
    lam_h *= 1 + 0.08 * elo_adj
    lam_a *= 1 - 0.08 * elo_adj

    # Monte Carlo from Poisson lambdas (vectorized).
    sims = 20_000
    hs = rng.poisson(lam_h, size=sims)
    aws = rng.poisson(lam_a, size=sims)
    home_win = float(np.mean(hs > aws))
    draw = float(np.mean(hs == aws))
    away_win = float(np.mean(hs < aws))
    over = float(np.mean(hs + aws > 2))
    under = float(np.mean(hs + aws <= 2))
    btts = float(np.mean((hs > 0) & (aws > 0)))
    pairs, counts = np.unique(np.stack([hs, aws], axis=1), axis=0, return_counts=True)
    top_idx = np.argsort(counts)[::-1][:5]
    top = [{"home": int(pairs[i][0]), "away": int(pairs[i][1]), "p": float(counts[i] / sims)} for i in top_idx]

    # Closed-form Poisson 1X2 for calibration mix.
    grid = range(0, 8)
    p_h = p_d = p_a = 0.0
    for i in grid:
        for j in grid:
            p = float(poisson.pmf(i, lam_h) * poisson.pmf(j, lam_a))
            if i > j:
                p_h += p
            elif i == j:
                p_d += p
            else:
                p_a += p
    mix_h = 0.5 * home_win + 0.5 * p_h
    mix_d = 0.5 * draw + 0.5 * p_d
    mix_a = 0.5 * away_win + 0.5 * p_a
    trees = tree_probs(tree_bundle, home, away, rating, stats)
    if trees:
        mix_h = 0.4 * mix_h + 0.6 * (0.5 * trees[0] + 0.5 * mix_h)
        mix_d = 0.4 * mix_d + 0.6 * (0.5 * trees[1] + 0.5 * mix_d)
        mix_a = 0.4 * mix_a + 0.6 * (0.5 * trees[2] + 0.5 * mix_a)
    s = mix_h + mix_d + mix_a or 1.0
    n = min(h["n"], a["n"])
    confidence = float(min(0.75, 0.25 + n / 40))
    return {
        "home_win": mix_h / s,
        "draw": mix_d / s,
        "away_win": mix_a / s,
        "over_25": over,
        "under_25": under,
        "btts": btts,
        "top_scorelines": top,
        "lambda_home": lam_h,
        "lambda_away": lam_a,
        "elo_home": elo_h,
        "elo_away": elo_a,
        "confidence": confidence,
        "xg": "UNKNOWN",
        "injuries": "UNKNOWN",
        "player_form": "UNKNOWN",
        "note": "xG and injuries are UNKNOWN without a dedicated event provider. Ensemble uses Poisson + Elo + Monte Carlo + (when enough PIT history exists) RandomForest/GBM.",
        "tree_ensemble": bool(trees),
    }


async def refresh(session: Session) -> dict[str, Any]:
    version = ensure_default_version(session, "FOOTBALL")
    tsdb = get_provider("thesportsdb")
    assert isinstance(tsdb, TheSportsDbProvider)
    source_status = []
    history: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    for league_id, name in THESPORTSDB_LEAGUES.items():
        past = await tsdb.past_events(league_id)
        nxt = await tsdb.next_events(league_id)
        source_status.append({"league": name, "past": past.status.value, "next": nxt.status.value, "past_error": past.error, "next_error": nxt.error})
        if past.ok:
            history.extend(past.payload)
        if nxt.ok:
            upcoming.extend(nxt.payload)

    for match in history + upcoming:
        existing = session.query(FootballMatch).filter(FootballMatch.external_id == match["external_id"]).one_or_none()
        kickoff = parse_timestamp(match.get("kickoff"))
        if existing:
            existing.status = match["status"]
            existing.home_goals = match.get("home_goals")
            existing.away_goals = match.get("away_goals")
            existing.payload = match
            existing.retrieved_at = utcnow()
        else:
            session.add(
                FootballMatch(
                    external_id=match["external_id"],
                    competition=match["competition"],
                    home=match["home"],
                    away=match["away"],
                    kickoff=kickoff,
                    status=match["status"],
                    home_goals=match.get("home_goals"),
                    away_goals=match.get("away_goals"),
                    source=match.get("source") or "thesportsdb",
                    payload=match,
                    data_quality="ok",
                )
            )

    rating, stats = _team_stats(history)
    rng = np.random.default_rng(20260902)
    tree_bundle = fit_tree_ensemble(history)
    predictions = []
    for match in upcoming:
        pred = predict_match(match["home"], match["away"], rating, stats, rng, tree_bundle)
        session.add(
            FootballPrediction(
                match_external_id=match["external_id"],
                home_win=pred["home_win"],
                draw=pred["draw"],
                away_win=pred["away_win"],
                over_25=pred["over_25"],
                under_25=pred["under_25"],
                btts=pred["btts"],
                top_scorelines=pred["top_scorelines"],
                confidence=pred["confidence"],
                model_version=version.version,
                explanation=pred,
            )
        )
        session.add(
            PredictionRecord(
                module=ModuleName.FOOTBALL.value,
                subject=match["external_id"],
                model_version=version.version,
                direction=max(("HOME", pred["home_win"]), ("DRAW", pred["draw"]), ("AWAY", pred["away_win"]), key=lambda x: x[1])[0],
                confidence=pred["confidence"],
                payload={**match, **pred},
            )
        )
        predictions.append({**match, **pred, "model_version": version.version})
    logger.info("football_refresh upcoming=%s history=%s", len(upcoming), len(history))
    return {
        "ok": True,
        "competitions": list(THESPORTSDB_LEAGUES.values()),
        "history_count": len(history),
        "upcoming_count": len(upcoming),
        "predictions": predictions,
        "source_status": source_status,
        "disclaimer": "Probabilities from statistical models on historical scores. Not a guaranteed result. Injuries/xG marked UNKNOWN when not sourced.",
        "model_version": version.version,
    }


def track_bet(
    session: Session,
    match_external_id: str,
    *,
    user_placed_bet: bool,
    market: str | None,
    selection: str | None,
    stake: Decimal | None,
    odds: Decimal | None,
) -> FootballBet:
    bet = FootballBet(
        match_external_id=match_external_id,
        tracked=True,
        user_placed_bet=user_placed_bet,
        market=market,
        selection=selection,
        stake=stake,
        odds=odds,
    )
    session.add(bet)
    return bet


def settle_bets(session: Session) -> int:
    settled = 0
    bets = session.query(FootballBet).filter(FootballBet.result.is_(None)).all()
    for bet in bets:
        match = session.query(FootballMatch).filter(FootballMatch.external_id == bet.match_external_id).one_or_none()
        if match is None or match.home_goals is None or match.away_goals is None:
            continue
        if not bet.user_placed_bet:
            bet.result = "NO_BET"
            continue
        if bet.stake is None or bet.odds is None or not bet.selection:
            bet.result = "INCOMPLETE"
            continue
        hg, ag = match.home_goals, match.away_goals
        won = False
        sel = bet.selection.upper()
        if sel in {"HOME", "1"} and hg > ag:
            won = True
        elif sel in {"DRAW", "X"} and hg == ag:
            won = True
        elif sel in {"AWAY", "2"} and hg < ag:
            won = True
        elif sel == "OVER_2.5" and (hg + ag) > 2:
            won = True
        elif sel == "UNDER_2.5" and (hg + ag) <= 2:
            won = True
        elif sel == "BTTS_YES" and hg > 0 and ag > 0:
            won = True
        if won:
            bet.result = "WIN"
            bet.payout = bet.stake * bet.odds
            bet.profit = bet.payout - bet.stake
        else:
            bet.result = "LOSS"
            bet.payout = Decimal("0")
            bet.profit = -bet.stake
        settled += 1
    return settled
