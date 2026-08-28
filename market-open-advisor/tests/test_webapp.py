from market_advisor.html_report import render_loading
from market_advisor.webapp import AppState, render_status_page


def test_loading_page_polls_status():
    html = render_loading("正在拉取上交所主板…", failed=False)
    assert "正在拉取上交所主板" in html
    assert "/status" in html
    assert "打开时刻个股操作建议" in html


def test_failed_loading_has_no_poll():
    html = render_loading("网络失败", failed=True)
    assert "网络失败" in html
    assert "setInterval" not in html


def test_status_page_uses_loading_until_done():
    state = AppState()
    state.message = "拟合中"
    html = render_status_page(state)
    assert "拟合中" in html
