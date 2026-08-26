"""T+1 share availability ledger.

Shares purchased on session T become sellable on the next trading session (T+1 rule).
Signals are generated after T close; execution is T+1; earliest exit is T+2.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class Lot:
    qty: int
    available_on: date  # first session the lot may be sold


@dataclass
class PositionLedger:
    symbol: str
    lots: list[Lot] = field(default_factory=list)

    @property
    def total_qty(self) -> int:
        return sum(lot.qty for lot in self.lots)

    def available_qty(self, session: date) -> int:
        return sum(lot.qty for lot in self.lots if lot.available_on <= session)

    def frozen_qty(self, session: date) -> int:
        return self.total_qty - self.available_qty(session)

    def buy(self, qty: int, session: date, sellable_on: date) -> None:
        if qty <= 0:
            return
        self.lots.append(Lot(qty=int(qty), available_on=sellable_on))

    def sell(self, qty: int, session: date) -> int:
        """Sell up to available quantity. Returns filled qty (may be less if T+1 frozen)."""
        remaining = int(qty)
        if remaining <= 0:
            return 0
        filled = 0
        new_lots: list[Lot] = []
        for lot in self.lots:
            if remaining <= 0 or lot.available_on > session:
                new_lots.append(lot)
                continue
            take = min(lot.qty, remaining)
            lot.qty -= take
            remaining -= take
            filled += take
            if lot.qty > 0:
                new_lots.append(lot)
        self.lots = new_lots
        return filled


class Book:
    def __init__(self) -> None:
        self._pos: dict[str, PositionLedger] = {}

    def ledger(self, symbol: str) -> PositionLedger:
        if symbol not in self._pos:
            self._pos[symbol] = PositionLedger(symbol=symbol)
        return self._pos[symbol]

    def total_qty(self, symbol: str) -> int:
        return self.ledger(symbol).total_qty

    def available_qty(self, symbol: str, session: date) -> int:
        return self.ledger(symbol).available_qty(session)

    def buy(self, symbol: str, qty: int, session: date, sellable_on: date) -> None:
        self.ledger(symbol).buy(qty, session, sellable_on)

    def sell(self, symbol: str, qty: int, session: date) -> int:
        return self.ledger(symbol).sell(qty, session)

    def symbols(self) -> list[str]:
        return [s for s, p in self._pos.items() if p.total_qty > 0]
