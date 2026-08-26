"""Position sizing with single-name, board, and book-level caps first."""

from __future__ import annotations

from dataclasses import dataclass

from ..config import Action, AppConfig, Board
from ..market.rules import round_lot


@dataclass
class BookState:
    nav: float
    gross_exposure: float
    names_held: int
    board_exposure: dict[str, float]
    weight_by_symbol: dict[str, float]


@dataclass
class SizingResult:
    action: Action
    shares: int
    notional: float
    weight: float
    reasons: list[str]


def size_long(
    *,
    cfg: AppConfig,
    nav: float,
    price: float,
    stop_distance_pct: float,
    adv_shares: float,
    board: Board | str,
    book: BookState,
    already_held: bool,
) -> SizingResult:
    reasons: list[str] = []
    if nav <= 0 or price <= 0:
        return SizingResult(Action.NO_TRADE, 0, 0.0, 0.0, ["invalid_price_or_nav"])

    board_key = board.value if isinstance(board, Board) else str(board)
    room_gross = cfg.risk.max_gross_exposure * nav - book.gross_exposure
    if room_gross <= price * cfg.market.lot_size:
        return SizingResult(Action.NO_TRADE, 0, 0.0, 0.0, ["gross_cap"])

    if not already_held and book.names_held >= cfg.risk.max_names_held:
        return SizingResult(Action.NO_TRADE, 0, 0.0, 0.0, ["max_names"])

    stop_d = max(float(stop_distance_pct), 0.008)
    risk_budget = cfg.risk.per_name_risk * nav
    shares_risk = risk_budget / (stop_d * price)
    shares_weight = (cfg.risk.max_single_weight * nav) / price
    board_used = book.board_exposure.get(board_key, 0.0)
    board_room = cfg.risk.max_board_weight * nav - board_used
    shares_board = max(0.0, board_room / price)
    shares_gross = max(0.0, room_gross / price)
    shares_liq = cfg.market.max_adv_participation * max(adv_shares, 0.0)

    shares = min(shares_risk, shares_weight, shares_board, shares_gross, shares_liq if shares_liq > 0 else shares_risk)
    qty = round_lot(shares, cfg.market.lot_size)
    if qty <= 0:
        return SizingResult(Action.NO_TRADE, 0, 0.0, 0.0, ["lot_or_liquidity"])

    notional = qty * price
    if notional < 1000:
        return SizingResult(Action.NO_TRADE, 0, 0.0, 0.0, ["notional_too_small"])

    reasons.append("risk_budget")
    if shares == shares_weight:
        reasons.append("single_cap")
    if abs(shares - shares_board) < 1:
        reasons.append("board_cap")
    return SizingResult(Action.BUY, qty, notional, notional / nav, reasons)
