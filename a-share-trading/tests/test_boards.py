from a_share_trading.boards import classify_board, tencent_symbol
from a_share_trading.markets import classify_market, match_market


def test_main_board_sse():
    info = classify_board("600519", "贵州茅台")
    assert info.exchange == "SSE"
    assert info.board == "主板"
    assert info.limit_pct == 0.10


def test_star_and_chinext():
    assert classify_board("688981", "中芯国际").limit_pct == 0.20
    assert classify_board("300750", "宁德时代").limit_pct == 0.20
    assert classify_board("301000", "某创业板").board == "创业板"


def test_st_and_bse():
    assert classify_board("000001", "*ST平安").limit_pct == 0.05
    assert classify_board("920000", "安徽凤凰").exchange == "BSE"
    assert classify_board("920000", "安徽凤凰").limit_pct == 0.30


def test_tencent_symbol():
    assert tencent_symbol("600519", "sh600519") == "sh600519"
    assert tencent_symbol("000001").startswith("sz")
    assert tencent_symbol("688111").startswith("sh")


def test_market_buckets():
    assert classify_market("SSE", "主板") == "上证"
    assert classify_market("SZSE", "主板") == "深证"
    assert classify_market("SSE", "科创板") == "科创板"
    assert classify_market("SZSE", "创业板") == "创业板"
    assert classify_market("BSE", "北交所") == "北交所"
    assert classify_market("SSE", "主板/ST") == "上证"
    assert match_market("SSE", "科创板", "科创板")
    assert not match_market("SSE", "科创板", "上证")
    assert match_market("SZSE", "主板", "深证")
