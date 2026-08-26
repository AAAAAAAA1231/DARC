"""Board classification and A-share code rules."""

from __future__ import annotations

import re

from ..config import Board

_ST_RE = re.compile(r"(ST|退|N\s|\*ST)", re.IGNORECASE)


def normalize_symbol(symbol: str) -> str:
    s = str(symbol).strip().upper().replace(".SH", "").replace(".SZ", "").replace(".SS", "")
    s = s.replace("SH", "").replace("SZ", "")
    digits = "".join(ch for ch in s if ch.isdigit())
    if not digits:
        raise ValueError(f"invalid symbol: {symbol}")
    return digits.zfill(6)


def infer_board(symbol: str) -> Board | None:
    code = normalize_symbol(symbol)
    if code.startswith("688"):
        return Board.STAR
    if code.startswith(("300", "301")):
        return Board.CHINEXT
    if code.startswith(("000", "001", "002", "003")):
        return Board.SZSE_MAIN
    if code.startswith(("600", "601", "603", "605")):
        return Board.SSE_MAIN
    return None


def is_supported_ashare(symbol: str) -> bool:
    return infer_board(symbol) is not None


def is_st_name(name: str | None) -> bool:
    if not name:
        return False
    return bool(_ST_RE.search(name))


def board_cn(board: Board) -> str:
    return {
        Board.SSE_MAIN: "上证主板",
        Board.SZSE_MAIN: "深证主板",
        Board.CHINEXT: "创业板",
        Board.STAR: "科创板",
    }[board]
