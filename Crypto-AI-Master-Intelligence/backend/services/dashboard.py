"""Homepage snapshot: live tickers + last persisted module results. No fabricated panels."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.core.config import get_settings
from backend.core.logging import get_logger
from backend.data_sources.binance import BinanceProvider
from backend.data_sources.registry import get_provider
from backend.database.orm import FootballMatch, FootballPrediction, FuturesPrediction, Project, ScoreHistory
from backend.services import btc_cycle as btc_svc
from backend.services import holdings as holdings_svc
from backend.services import notifications as notify_svc
from backend.services import portfolio as portfolio_svc

logger = get_logger("dashboard")


async def build(session: Session) -> dict[str, Any]:
    volume_top, ticker_status = await _futures_volume_top()
    cycle = await btc_svc.latest_or_analyze(session)
    port = await portfolio_svc.dashboard(session)
    for pos in port.get("positions") or []:
        if "current_model_signal" not in pos:
            roi = pos.get("roi")
            pos["current_model_signal"] = holdings_svc.holding_signal(roi if isinstance(roi, float) else None, None)
    notes = notify_svc.list_unread(session)
    return {
        "market_regime": cycle.get("regime"),
        "btc_cycle": cycle,
        "portfolio": port,
        "holdings_overlay": holdings_svc.from_summaries(port.get("positions") or []),
        "futures_volume_top": volume_top,
        "futures_analyzed_top": _latest_futures(session),
        "radar_latest": _latest_radar(session),
        "football_latest": _latest_football(session),
        "notifications": [{"id": n.id, "title": n.title, "body": n.body, "kind": n.kind} for n in notes],
        "ticker_status": ticker_status,
        "disclaimer": get_settings().disclaimer,
    }


async def _futures_volume_top() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    try:
        provider = get_provider("binance")
    except KeyError:
        return [], {"status": "not_registered"}
    assert isinstance(provider, BinanceProvider)
    env = await provider.futures_ticker_24h()
    if not env.ok:
        return [], env.as_dict()
    rows = [
        {"rank": i, "symbol": r["symbol"], "last": r["last"], "quote_volume": r["quote_volume"], "change_pct": r.get("price_change_pct")}
        for i, r in enumerate(env.payload[:3], start=1)
    ]
    return rows, {"status": env.status.value, "universe": len(env.payload)}


def _latest_futures(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(select(FuturesPrediction).order_by(FuturesPrediction.created_at.desc()).limit(9)).scalars().all()
    # keep latest rank 1-3 from the newest batch
    seen = set()
    out = []
    for r in rows:
        if r.rank in seen:
            continue
        seen.add(r.rank)
        out.append(
            {
                "rank": r.rank,
                "symbol": r.symbol,
                "direction": r.direction,
                "confidence": float(r.confidence) if r.confidence is not None else None,
                "current_price": str(r.current_price) if r.current_price is not None else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
        )
        if len(out) >= 3:
            break
    return sorted(out, key=lambda x: x.get("rank") or 99)


def _latest_radar(session: Session) -> list[dict[str, Any]]:
    rows = (
        session.execute(
            select(ScoreHistory)
            .where(ScoreHistory.module == "50X")
            .order_by(ScoreHistory.created_at.desc())
            .limit(40)
        )
        .scalars()
        .all()
    )
    latest_by_project: dict[str, ScoreHistory] = {}
    for row in rows:
        latest_by_project.setdefault(row.project_id, row)
    ranked = []
    for pid, row in latest_by_project.items():
        scores = row.scores or {}
        if scores.get("security_verdict") in {"MALICIOUS", "HIGH_RISK", "UNKNOWN"}:
            continue
        score = scores.get("score_50x")
        if score is None:
            continue
        project = session.execute(select(Project).where(Project.project_id == pid)).scalar_one_or_none()
        if project and project.hidden:
            continue
        ranked.append(
            {
                "project_id": pid,
                "name": project.name if project else pid,
                "symbol": project.symbol if project else None,
                "score": score,
                "security": scores.get("security_verdict"),
                "grade": scores.get("grade"),
                "signal": row.signal,
            }
        )
    ranked.sort(key=lambda x: x["score"], reverse=True)
    return ranked[:10]


def _latest_football(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(select(FootballPrediction).order_by(FootballPrediction.created_at.desc()).limit(6)).scalars().all()
    out = []
    for r in rows:
        match = session.execute(select(FootballMatch).where(FootballMatch.external_id == r.match_external_id)).scalar_one_or_none()
        out.append(
            {
                "match": r.match_external_id,
                "home": match.home if match else None,
                "away": match.away if match else None,
                "kickoff": match.kickoff.isoformat() if match and match.kickoff else None,
                "home_win": float(r.home_win),
                "draw": float(r.draw),
                "away_win": float(r.away_win),
                "confidence": float(r.confidence),
            }
        )
    return out
