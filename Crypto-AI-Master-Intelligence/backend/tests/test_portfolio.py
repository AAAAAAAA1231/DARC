from datetime import timedelta
from decimal import Decimal

from backend.core.enums import PositionStatus
from backend.core.parsing import utcnow
from backend.database.orm import PortfolioSnapshot
from backend.database.session import SessionLocal
from backend.services.portfolio import _period_delta, record_fill, summarize_position


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


def test_period_pnl_none_without_snapshots():
    session = SessionLocal()
    try:
        today, week, month = _period_delta(session, None, Decimal("10"))
        assert today is None
        assert week is None
        assert month is None
    finally:
        session.close()


def test_period_pnl_uses_earliest_snapshot_in_window():
    session = SessionLocal()
    try:
        session.add(
            PortfolioSnapshot(
                as_of=utcnow() - timedelta(hours=3),
                module=None,
                invested=Decimal("100"),
                current_value=Decimal("110"),
                net_pnl=Decimal("10"),
                roi=0.1,
            )
        )
        session.add(
            PortfolioSnapshot(
                as_of=utcnow() - timedelta(minutes=5),
                module=None,
                invested=Decimal("100"),
                current_value=Decimal("112"),
                net_pnl=Decimal("12"),
                roi=0.12,
            )
        )
        session.flush()
        today, week, month = _period_delta(session, None, Decimal("15"))
        assert today == Decimal("5")
        assert week == Decimal("5")
        assert month == Decimal("5")
    finally:
        session.close()


def test_period_windows_are_independent():
    session = SessionLocal()
    try:
        session.add(
            PortfolioSnapshot(
                as_of=utcnow() - timedelta(days=10),
                module=None,
                invested=Decimal("100"),
                current_value=Decimal("101"),
                net_pnl=Decimal("1"),
            )
        )
        session.add(
            PortfolioSnapshot(
                as_of=utcnow() - timedelta(hours=1),
                module=None,
                invested=Decimal("100"),
                current_value=Decimal("104"),
                net_pnl=Decimal("4"),
            )
        )
        session.flush()
        today, week, month = _period_delta(session, None, Decimal("10"))
        assert today == Decimal("6")
        assert week == Decimal("6")
        assert month == Decimal("9")
    finally:
        session.close()

