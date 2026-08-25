from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoardInfo:
    exchange: str
    board: str
    limit_pct: float
    lot_size: int


def classify_board(code: str, name: str = "") -> BoardInfo:
    """Map A-share ticker rules onto exchange, board, and daily limit."""
    code = (code or "").strip()
    name = name or ""
    st = "ST" in name.upper() or name.startswith("*ST") or name.startswith("S*ST")
    ipo_open = name.startswith("N") or name.startswith("C")

    if code.startswith(("4", "8", "9")):
        info = BoardInfo("BSE", "北交所", 0.30, 100)
    elif code.startswith(("688", "689")):
        info = BoardInfo("SSE", "科创板", 0.20, 200)
    elif code.startswith(("300", "301")):
        info = BoardInfo("SZSE", "创业板", 0.20, 100)
    elif code.startswith(("000", "001", "002", "003")):
        info = BoardInfo("SZSE", "主板", 0.10, 100)
    elif code.startswith(("600", "601", "603", "605")):
        info = BoardInfo("SSE", "主板", 0.10, 100)
    elif code.startswith("60"):
        info = BoardInfo("SSE", "主板", 0.10, 100)
    else:
        info = BoardInfo("UNKNOWN", "未知", 0.10, 100)

    if st:
        return BoardInfo(info.exchange, info.board + "/ST", 0.05, info.lot_size)
    if ipo_open:
        return BoardInfo(info.exchange, info.board + "/新股", 1.0, info.lot_size)
    return info


def tencent_symbol(code: str, sina_symbol: str | None = None) -> str:
    if sina_symbol:
        return sina_symbol
    if code.startswith(("4", "8", "9")):
        return f"bj{code}"
    if code.startswith(("000", "001", "002", "003", "300", "301")):
        return f"sz{code}"
    return f"sh{code}"
