"""Re-score open positions. Signals are advice only — never routed to an exchange."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import PositionStatus
from backend.database.orm import PortfolioPosition
from backend.services.portfolio import mark_price, summarize_position


def holding_signal(unrealized_roi: float | None, security_verdict: str | None) -> str:
    if security_verdict in {"MALICIOUS", "HIGH_RISK"}:
        return "HIGH_RISK"
    if unrealized_roi is None:
        return "HOLD"
    if unrealized_roi >= 0.4:
        return "TAKE_PROFIT"
    if unrealized_roi >= 0.15:
        return "REDUCE"
    if unrealized_roi <= -0.25:
        return "EXIT"
    if unrealized_roi <= -0.08:
        return "REDUCE"
    if 0.05 <= unrealized_roi <= 0.12:
        return "ADD"
    return "HOLD"


async def reevaluate_open(session: Session) -> list[dict[str, Any]]:
    rows = (
        session.query(PortfolioPosition)
        .filter(PortfolioPosition.status.in_([PositionStatus.OPEN.value, PositionStatus.PARTIAL_EXIT.value]))
        .all()
    )
    out = []
    for pos in rows:
        last, meta = await mark_price(pos.symbol)
        summary = summarize_position(session, pos, last)
        roi = summary.get("roi")
        signal = holding_signal(roi, None)
        out.append(
            {
                **summary,
                "current_model_signal": signal,
                "price_meta": meta,
                "note": "Advisory only. The system never places live orders.",
            }
        )
    return out
