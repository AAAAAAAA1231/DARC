from __future__ import annotations


def classify_market(exchange: str, board: str) -> str:
    """Mutually exclusive A-share bucket: 上证 / 深证 / 科创板 / 创业板 / 北交所."""
    board = board or ""
    exchange = exchange or ""
    if "科创板" in board:
        return "科创板"
    if "创业板" in board:
        return "创业板"
    if exchange == "BSE" or "北交所" in board:
        return "北交所"
    if exchange == "SSE":
        return "上证"
    if exchange == "SZSE":
        return "深证"
    return "其他"


def match_market(exchange: str, board: str, selected: str) -> bool:
    if not selected:
        return True
    return classify_market(exchange, board) == selected
