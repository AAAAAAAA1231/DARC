"""Money helpers using Decimal only."""

from decimal import Decimal

ZERO = Decimal("0")


def d(value: str | int | float | Decimal) -> Decimal:
    return Decimal(str(value))
