from decimal import Decimal

from backend.core.enums import PositionStatus
from backend.database.session import SessionLocal
from backend.services.portfolio import record_fill, summarize_position


def test_average_cost_and_fees():
    session = SessionLocal()
    try:
        pos = record_fill(
            session,
            module="SPOT",
            symbol="TESTUSDT",
            side="BUY",
            quantity=Decimal("2"),
            price=Decimal("10"),
            fee=Decimal("0.2"),
        )
        record_fill(
            session,
            module="SPOT",
            symbol="TESTUSDT",
            side="BUY",
            quantity=Decimal("2"),
            price=Decimal("20"),
            fee=Decimal("0.2"),
        )
        session.flush()
        summary = summarize_position(session, pos, last=Decimal("30"))
        assert Decimal(summary["avg_cost"]) == Decimal("15")
        assert Decimal(summary["invested"]) == Decimal("60")
        assert Decimal(summary["quantity"]) == Decimal("4")
        assert Decimal(summary["total_cost"]) == Decimal("0.4")
        assert Decimal(summary["current_value"]) == Decimal("120")
        assert Decimal(summary["unrealized_pnl"]) == Decimal("60")
        assert Decimal(summary["net_pnl"]) == Decimal("59.6")
        record_fill(
            session,
            module="SPOT",
            symbol="TESTUSDT",
            side="SELL",
            quantity=Decimal("4"),
            price=Decimal("30"),
            fee=Decimal("0.1"),
        )
        session.flush()
        assert pos.status == PositionStatus.CLOSED.value
    finally:
        session.close()
