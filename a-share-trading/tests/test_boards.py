from a_share_trading.boards import classify_board, tencent_symbol


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
