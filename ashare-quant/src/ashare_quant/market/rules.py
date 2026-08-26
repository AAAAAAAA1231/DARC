"""A-share microstructure: price limits, lot size, T+1, fill probability."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from ..config import Board, LimitStatus, MarketConfig
from ..universe.boards import infer_board


def limit_ratio(
    board: Board,
    *,
    is_st: bool = False,
    listing_days: int | None = None,
    cfg: MarketConfig | None = None,
) -> float:
    cfg = cfg or MarketConfig()
    if listing_days is not None and listing_days < cfg.ipo_no_limit_days:
        return 10.0  # effectively no daily limit
    if is_st:
        return cfg.st_limit
    if board == Board.CHINEXT:
        return cfg.chinext_limit
    if board == Board.STAR:
        return cfg.star_limit
    return cfg.main_limit


def limit_prices(prev_close: float, ratio: float) -> tuple[float, float]:
    if prev_close <= 0 or not np.isfinite(prev_close):
        return (np.nan, np.nan)
    up = round(prev_close * (1.0 + ratio) + 1e-12, 2)
    down = round(prev_close * (1.0 - ratio) + 1e-12, 2)
    return up, down


def classify_limit(
    open_: float,
    high: float,
    low: float,
    close: float,
    prev_close: float,
    ratio: float,
    tick: float = 0.01,
) -> LimitStatus:
    up, down = limit_prices(prev_close, ratio)
    if not np.isfinite(up):
        return LimitStatus.NORMAL
    eps = tick / 2
    sealed_up = (
        abs(open_ - up) <= eps
        and abs(high - up) <= eps
        and abs(low - up) <= eps
        and abs(close - up) <= eps
    )
    sealed_down = (
        abs(open_ - down) <= eps
        and abs(high - down) <= eps
        and abs(low - down) <= eps
        and abs(close - down) <= eps
    )
    if sealed_up:
        return LimitStatus.SEALED_UP
    if sealed_down:
        return LimitStatus.SEALED_DOWN
    if high + eps >= up:
        return LimitStatus.TOUCH_UP
    if low - eps <= down:
        return LimitStatus.TOUCH_DOWN
    return LimitStatus.NORMAL


def round_lot(shares: float, lot_size: int = 100) -> int:
    if shares <= 0:
        return 0
    return int(shares // lot_size) * lot_size


def fill_probability(
    side: str,
    status: LimitStatus,
    *,
    cfg: MarketConfig | None = None,
    order_volume: float = 0.0,
    day_volume: float = 0.0,
) -> float:
    """Heuristic fill model. Sealed limit-up cannot be bought; sealed limit-down cannot be sold."""
    cfg = cfg or MarketConfig()
    side = side.lower()
    if day_volume <= 0:
        return 0.0
    if side == "buy" and status == LimitStatus.SEALED_UP:
        return cfg.sealed_limit_fill_prob
    if side == "sell" and status == LimitStatus.SEALED_DOWN:
        return cfg.sealed_limit_fill_prob
    if side == "buy" and status == LimitStatus.TOUCH_UP:
        base = cfg.touch_limit_fill_prob
    elif side == "sell" and status == LimitStatus.TOUCH_DOWN:
        base = cfg.touch_limit_fill_prob
    else:
        base = 1.0
    if day_volume > 0 and order_volume > 0:
        participation = min(1.0, order_volume / day_volume)
        cap = min(1.0, cfg.max_adv_participation / max(participation, 1e-9) * 50)
        base *= min(1.0, 1.0 - 0.5 * participation)
        base = min(base, cap)
    return float(np.clip(base, 0.0, 1.0))


def apply_limit_clip(ohlc: pd.DataFrame, prev_close: pd.Series, ratio: pd.Series) -> pd.DataFrame:
    up = (prev_close * (1.0 + ratio)).round(2)
    down = (prev_close * (1.0 - ratio)).round(2)
    out = ohlc.copy()
    for col in ("open", "high", "low", "close"):
        out[col] = out[col].clip(lower=down, upper=up)
    out["high"] = np.maximum(out["high"], out[["open", "close"]].max(axis=1))
    out["low"] = np.minimum(out["low"], out[["open", "close"]].min(axis=1))
    return out


def board_of_row(symbol: str, board_value: str | None = None) -> Board:
    if board_value:
        return Board(board_value)
    inferred = infer_board(symbol)
    if inferred is None:
        raise ValueError(f"unsupported symbol {symbol}")
    return inferred


def listing_days_on(listing_date: date, asof: date) -> int:
    return max(0, (asof - listing_date).days)
