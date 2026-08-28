from market_advisor.markets import MARKET_BY_KEY
from market_advisor.universe import code_belongs, parse_sina_board, skip_name, us_instruments


def test_code_belongs_filters_boards():
    assert code_belongs("sse", "600519")
    assert not code_belongs("sse", "300750")
    assert code_belongs("szse", "000001")
    assert not code_belongs("szse", "300308")
    assert code_belongs("chinext", "300308")
    assert code_belongs("star", "688256")
    assert code_belongs("bse", "920288")


def test_skip_st_and_new_listings():
    assert skip_name("*ST宁科")
    assert skip_name("ST海投")
    assert skip_name("N华大")
    assert not skip_name("贵州茅台")


def test_parse_sina_board_keeps_matching_codes_only():
    market = MARKET_BY_KEY["sse"]
    rows = [
        {"symbol": "sh600519", "code": "600519", "name": "贵州茅台"},
        {"symbol": "sh688256", "code": "688256", "name": "寒武纪"},
        {"symbol": "sz000001", "code": "000001", "name": "平安银行"},
        {"symbol": "sh600000", "code": "600000", "name": "浦发银行"},
    ]
    out = parse_sina_board(rows, market, limit=10)
    assert [item.symbol for item in out] == ["600519", "600000"]
    assert out[0].tencent == "sh600519"
    assert out[0].yahoo == "600519.SS"


def test_us_book_has_tickers():
    names = [item.symbol for item in us_instruments(3)]
    assert names == ["AAPL", "MSFT", "NVDA"]
