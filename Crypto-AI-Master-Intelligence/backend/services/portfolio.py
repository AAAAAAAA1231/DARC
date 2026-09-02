"""Portfolio ledger. Model recommendation, user fills, and mark-to-market stay separate."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import ModuleName, PositionStatus
from backend.core.logging import get_logger
from backend.core.parsing import parse_decimal, parse_timestamp, utcnow, ensure_aware
from backend.database.orm import PortfolioPosition, PortfolioTransaction, UserAction
from backend.data_sources.binance import BinanceProvider
from backend.data_sources.registry import get_provider

logger = get_logger("portfolio")

ZERO = Decimal("0")


def _d(value: Any) -> Decimal:
    parsed = parse_decimal(value)
    return parsed if parsed is not None else ZERO


def record_fill(
    session: Session,
    *,
    module: str,
    symbol: str,
    side: str,
    quantity: Decimal,
    price: Decimal,
    fee: Decimal = ZERO,
    funding_fee: Decimal = ZERO,
    gas: Decimal = ZERO,
    slippage: Decimal = ZERO,
    other_cost: Decimal = ZERO,
    venue: str | None = None,
    wallet: str | None = None,
    executed_at: datetime | None = None,
    project_id: str | None = None,
    note: str | None = None,
    original_model_score: float | None = None,
    original_model_version: str | None = None,
) -> PortfolioPosition:
    if wallet and len(wallet) > 128:
        raise ValueError("wallet must be a public address, not a key material blob")
    side_n = side.upper()
    if side_n not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    position = (
        session.query(PortfolioPosition)
        .filter(
            PortfolioPosition.symbol == symbol,
            PortfolioPosition.module == module,
            PortfolioPosition.status.in_([PositionStatus.OPEN.value, PositionStatus.PARTIAL_EXIT.value, PositionStatus.NO_POSITION.value]),
        )
        .order_by(PortfolioPosition.opened_at.desc())
        .first()
    )
    if position is None:
        position = PortfolioPosition(
            project_id=project_id,
            module=module,
            symbol=symbol,
            status=PositionStatus.OPEN.value,
            quantity=ZERO,
            avg_cost=ZERO,
            invested=ZERO,
            fees=ZERO,
            realized_pnl=ZERO,
            venue=venue,
            wallet=wallet,
            original_model_score=original_model_score,
            original_model_version=original_model_version,
            note=note,
        )
        session.add(position)
        session.flush()

    tx = PortfolioTransaction(
        position_id=position.id,
        side=side_n,
        quantity=quantity,
        price=price,
        fee=fee,
        funding_fee=funding_fee,
        gas=gas,
        slippage=slippage,
        other_cost=other_cost,
        venue=venue,
        wallet=wallet,
        executed_at=executed_at or utcnow(),
        note=note,
    )
    session.add(tx)
    costs = fee + funding_fee + gas + slippage + other_cost
    position.fees = (position.fees or ZERO) + costs

    if side_n == "BUY":
        new_qty = (position.quantity or ZERO) + quantity
        cash = quantity * price
        position.invested = (position.invested or ZERO) + cash
        if new_qty > 0:
            position.avg_cost = ((position.quantity or ZERO) * (position.avg_cost or ZERO) + cash) / new_qty
        position.quantity = new_qty
        position.status = PositionStatus.OPEN.value
    else:
        sell_qty = min(quantity, position.quantity or ZERO)
        proceeds = sell_qty * price
        cost_basis = sell_qty * (position.avg_cost or ZERO)
        position.realized_pnl = (position.realized_pnl or ZERO) + (proceeds - cost_basis)
        position.quantity = (position.quantity or ZERO) - sell_qty
        if position.quantity <= 0:
            position.quantity = ZERO
            position.status = PositionStatus.CLOSED.value
            position.closed_at = utcnow()
        else:
            position.status = PositionStatus.PARTIAL_EXIT.value

    session.add(UserAction(action=f"fill_{side_n.lower()}", project_id=project_id, payload={"symbol": symbol, "qty": str(quantity)}))
    logger.info("fill module=%s symbol=%s side=%s qty=%s", module, symbol, side_n, quantity)
    return position


def _total_costs(session: Session, position_id: int) -> Decimal:
    txs = session.query(PortfolioTransaction).filter(PortfolioTransaction.position_id == position_id).all()
    return sum((t.fee + t.funding_fee + t.gas + t.slippage + t.other_cost for t in txs), ZERO)


async def mark_price(symbol: str) -> tuple[Decimal | None, dict[str, Any]]:
    provider = get_provider("binance")
    assert isinstance(provider, BinanceProvider)
    pair = symbol if symbol.endswith("USDT") else f"{symbol}USDT"
    tickers = await provider.spot_ticker_24h()
    if not tickers.ok:
        fut = await provider.futures_ticker_24h()
        if not fut.ok:
            return None, {"spot": tickers.as_dict(), "futures": fut.as_dict()}
        rows = fut.payload
        source = fut
    else:
        rows = tickers.payload
        source = tickers
    match = next((r for r in rows if r["symbol"] == pair or r["symbol"] == symbol), None)
    if not match:
        return None, {"source": source.as_dict(), "error": f"symbol {symbol} not on Binance ticker"}
    return _d(match["last"]), {"source": source.source, "symbol": match["symbol"]}


def summarize_position(session: Session, position: PortfolioPosition, last: Decimal | None) -> dict[str, Any]:
    qty = position.quantity or ZERO
    invested = position.invested or ZERO
    realized = position.realized_pnl or ZERO
    costs = _total_costs(session, position.id)
    current_value = (qty * last) if last is not None else None
    unrealized = (current_value - qty * (position.avg_cost or ZERO)) if current_value is not None else None
    gross = None
    if current_value is not None:
        gross = realized + (unrealized or ZERO)
    net = (gross - costs) if gross is not None else None
    denom = invested + costs
    roi = float(net / denom) if net is not None and denom > 0 else None
    holding = None
    if position.opened_at:
        delta = utcnow() - ensure_aware(position.opened_at)
        holding = int(delta.total_seconds() // 3600)
    return {
        "id": position.id,
        "project_id": position.project_id,
        "module": position.module,
        "symbol": position.symbol,
        "status": position.status,
        "quantity": str(qty),
        "avg_cost": str(position.avg_cost or ZERO),
        "invested": str(invested),
        "current_price": str(last) if last is not None else None,
        "current_value": str(current_value) if current_value is not None else None,
        "realized_pnl": str(realized),
        "unrealized_pnl": str(unrealized) if unrealized is not None else None,
        "gross_pnl": str(gross) if gross is not None else None,
        "total_cost": str(costs),
        "net_pnl": str(net) if net is not None else None,
        "roi": roi,
        "holding_hours": holding,
        "venue": position.venue,
        "wallet": position.wallet,
        "original_model_score": float(position.original_model_score) if position.original_model_score is not None else None,
        "original_model_version": position.original_model_version,
        "opened_at": position.opened_at.isoformat() if position.opened_at else None,
    }


async def dashboard(session: Session, module: str | None = None) -> dict[str, Any]:
    q = session.query(PortfolioPosition)
    if module:
        q = q.filter(PortfolioPosition.module == module)
    positions = q.all()
    items = []
    invested = ZERO
    current = ZERO
    realized = ZERO
    unrealized = ZERO
    costs = ZERO
    missing_prices: list[str] = []
    for pos in positions:
        last, meta = await mark_price(pos.symbol)
        if last is None:
            missing_prices.append(pos.symbol)
        summary = summarize_position(session, pos, last)
        items.append({**summary, "price_meta": meta})
        invested += _d(summary["invested"])
        realized += _d(summary["realized_pnl"])
        costs += _d(summary["total_cost"])
        if summary["current_value"] is not None:
            current += _d(summary["current_value"])
        if summary["unrealized_pnl"] is not None:
            unrealized += _d(summary["unrealized_pnl"])
    gross = realized + unrealized
    net = gross - costs
    roi = float(net / (invested + costs)) if (invested + costs) > 0 else None
    return {
        "total_invested": str(invested),
        "current_value": str(current),
        "realized_pnl": str(realized),
        "unrealized_pnl": str(unrealized),
        "gross_pnl": str(gross),
        "total_cost": str(costs),
        "net_pnl": str(net),
        "roi": roi,
        "today_pnl": None,
        "week_pnl": None,
        "month_pnl": None,
        "period_note": "Intraday/week/month PnL requires marked snapshots; those series are not invented when absent.",
        "positions": items,
        "missing_prices": missing_prices,
        "modules": [m.value for m in ModuleName],
    }
