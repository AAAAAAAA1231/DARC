"""Lottery frequency + vectorized Monte Carlo. Explicitly random; never a guarantee."""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.data_sources.lottery import LotteryProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import LotteryPrediction, LotteryResult
from backend.services.model_center import ensure_default_version
from backend.simulations.monte_carlo import lottery_coverage_sim

logger = get_logger("lottery")

DISCLAIMER = (
    "Lottery draws are random. Historical frequency and Monte Carlo coverage are descriptive statistics, "
    "not a method that guarantees a prize. Simulation count is not accuracy."
)


async def refresh(session: Session, game: str = "ssq") -> dict[str, Any]:
    version = ensure_default_version(session, "LOTTERY")
    provider = get_provider("lottery")
    assert isinstance(provider, LotteryProvider)
    env = await provider.history(game, count=50)
    if not env.ok:
        return {"ok": False, "source_status": env.as_dict(), "disclaimer": DISCLAIMER, "draws": []}
    for row in env.payload:
        existing = (
            session.query(LotteryResult)
            .filter(LotteryResult.game == row["game"], LotteryResult.issue == row["issue"])
            .one_or_none()
        )
        if existing:
            continue
        session.add(
            LotteryResult(
                game=row["game"],
                issue=row["issue"],
                numbers=row["numbers"],
                source=row.get("source") or "lottery",
                data_quality="ok",
            )
        )
    freqs = _frequencies(env.payload, game)
    recs = _recommend(freqs, game)
    session.add(
        LotteryPrediction(
            game=game,
            combinations={"recommended": recs},
            frequencies=freqs,
            coverage=None,
            risk="HIGH — lottery is random",
            disclaimer=DISCLAIMER,
            model_version=version.version,
        )
    )
    return {
        "ok": True,
        "game": game,
        "draws": env.payload,
        "frequencies": freqs,
        "recommended_combinations": recs,
        "risk": "HIGH",
        "disclaimer": DISCLAIMER,
        "source_status": {
            "status": env.status.value,
            "n": len(env.payload),
            "error": env.error,
            "meta": {k: v for k, v in (env.meta or {}).items() if k != "body"},
        },
        "model_version": version.version,
    }


def _frequencies(draws: list[dict[str, Any]], game: str) -> dict[str, Any]:
    if game == "ssq":
        reds: list[str] = []
        blues: list[str] = []
        for d in draws:
            reds.extend(d["numbers"].get("red") or [])
            blues.extend(d["numbers"].get("blue") or [])
        return {"red": Counter(reds).most_common(), "blue": Counter(blues).most_common()}
    if game == "dlt":
        front: list[str] = []
        back: list[str] = []
        for d in draws:
            front.extend(d["numbers"].get("front") or [])
            back.extend(d["numbers"].get("back") or [])
        return {"front": Counter(front).most_common(), "back": Counter(back).most_common()}
    if game in {"3d", "pl3", "pl5", "qxc"}:
        digits: list[str] = []
        for d in draws:
            digits.extend(d["numbers"].get("digits") or d["numbers"].get("numbers") or [])
        return {"digits": Counter(digits).most_common()}
    return {}


def _recommend(freqs: dict[str, Any], game: str) -> list[dict[str, Any]]:
    """Highest historical frequency combinations — still random going forward."""
    if game == "ssq" and freqs.get("red") and freqs.get("blue"):
        red = [n for n, _ in freqs["red"][:12]]
        blue = [n for n, _ in freqs["blue"][:4]]
        combos = []
        for i in range(0, min(6, max(0, len(red) - 5))):
            combos.append({"red": sorted(red[i : i + 6], key=lambda x: int(x)), "blue": blue[i % len(blue)]})
        return combos
    if game == "dlt" and freqs.get("front") and freqs.get("back"):
        front = [n for n, _ in freqs["front"][:10]]
        back = [n for n, _ in freqs["back"][:4]]
        return [{"front": front[:5], "back": back[:2]}]
    if freqs.get("digits"):
        width = {"3d": 3, "pl3": 3, "pl5": 5, "qxc": 7}.get(game, 3)
        pool = [n for n, _ in freqs["digits"][: max(width, 6)]]
        return [{"digits": pool[:width], "note": "frequency sample only — lottery remains random"}]
    return []


def run_simulation(session: Session, game: str, paths: int, simulation_id: str) -> dict[str, Any]:
    draws = session.query(LotteryResult).filter(LotteryResult.game == game).all()
    historical = [d.numbers for d in draws]
    if not historical:
        return {"ok": False, "error": "no historical draws stored", "disclaimer": DISCLAIMER}
    result = lottery_coverage_sim(game, historical, paths)
    result["disclaimer"] = DISCLAIMER
    result["simulation_confidence"] = "paths increase estimate precision of a random process, not win probability skill"
    result["statistical_confidence"] = result.get("ci")
    result["historical_backtest_accuracy"] = None
    result["out_of_sample_performance"] = None
    result["live_performance"] = None
    return result
