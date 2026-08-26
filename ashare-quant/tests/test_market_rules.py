from datetime import date

from ashare_quant.config import Board, CostConfig, MarketConfig
from ashare_quant.calendar import next_trading_day, shift_trading_days
from ashare_quant.market.costs import trade_cost
from ashare_quant.market.rules import classify_limit, fill_probability, limit_ratio, round_lot
from ashare_quant.market.t_plus_one import Book
from ashare_quant.config import LimitStatus


def test_limit_ratios():
    cfg = MarketConfig()
    assert limit_ratio(Board.SSE_MAIN, cfg=cfg) == 0.10
    assert limit_ratio(Board.SZSE_MAIN, cfg=cfg) == 0.10
    assert limit_ratio(Board.CHINEXT, cfg=cfg) == 0.20
    assert limit_ratio(Board.STAR, cfg=cfg) == 0.20
    assert limit_ratio(Board.SSE_MAIN, is_st=True, cfg=cfg) == 0.05
    assert limit_ratio(Board.STAR, listing_days=2, cfg=cfg) > 1.0


def test_sealed_limit_up_cannot_buy():
    st = classify_limit(11.0, 11.0, 11.0, 11.0, 10.0, 0.10)
    assert st is LimitStatus.SEALED_UP
    assert fill_probability("buy", st, day_volume=1e6, order_volume=1000) == 0.0
    st_dn = classify_limit(9.0, 9.0, 9.0, 9.0, 10.0, 0.10)
    assert st_dn is LimitStatus.SEALED_DOWN
    assert fill_probability("sell", st_dn, day_volume=1e6, order_volume=1000) == 0.0


def test_lot_size():
    assert round_lot(250, 100) == 200
    assert round_lot(99, 100) == 0


def test_stamp_tax_sell_only_and_commission_floor():
    cfg = CostConfig()
    buy = trade_cost(1000, "buy", cfg, atr_pct=0.02)
    sell = trade_cost(1000, "sell", cfg, atr_pct=0.02)
    assert buy["stamp_tax"] == 0.0
    assert sell["stamp_tax"] > 0
    assert buy["commission"] >= cfg.commission_min
    assert sell["total"] > buy["total"]


def test_t_plus_one_cannot_sell_same_session():
    book = Book()
    session = date(2024, 3, 4)
    sellable = next_trading_day(session)
    book.buy("600000", 1000, session, sellable)
    assert book.available_qty("600000", session) == 0
    assert book.sell("600000", 1000, session) == 0
    assert book.total_qty("600000") == 1000
    assert book.available_qty("600000", sellable) == 1000
    assert book.sell("600000", 400, sellable) == 400
    assert book.total_qty("600000") == 600


def test_signal_to_exit_calendar_is_t_plus_2():
    signal = date(2024, 3, 4)  # Monday
    exec_d = next_trading_day(signal)
    exit_d = next_trading_day(exec_d)
    assert exec_d == date(2024, 3, 5)
    assert exit_d == date(2024, 3, 6)
    assert shift_trading_days(signal, 2) == exit_d
