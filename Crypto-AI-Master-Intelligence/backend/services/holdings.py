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


def from_summaries(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Map open positions by BTCUSDT and BTC so radar/spot/asset pages can overlay cost and PnL."""
    out: dict[str, Any] = {}
    for summary in rows:
        status = (summary.get("status") or "").upper()
        if status not in {PositionStatus.OPEN.value, PositionStatus.PARTIAL_EXIT.value}:
            continue
        roi = summary.get("roi")
        payload = {
            "held": True,
            "position_id": summary.get("id"),
            "symbol": summary.get("symbol"),
            "quantity": summary.get("quantity"),
            "avg_cost": summary.get("avg_cost"),
            "net_pnl": summary.get("net_pnl"),
            "unrealized_pnl": summary.get("unrealized_pnl"),
            "current_price": summary.get("current_price"),
            "roi": roi,
            "signal": summary.get("current_model_signal") or holding_signal(roi if isinstance(roi, float) else None, None),
            "status": summary.get("status"),
        }
        symbol = (summary.get("symbol") or "").upper()
        if not symbol:
            continue
        out[symbol] = payload
        if symbol.endswith("USDT"):
            out[symbol[:-4]] = payload
        elif not symbol.endswith("USDT"):
            out[f"{symbol}USDT"] = payload
    return out


async def overlay_map(session: Session) -> dict[str, Any]:
    return from_summaries(await reevaluate_open(session))


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
