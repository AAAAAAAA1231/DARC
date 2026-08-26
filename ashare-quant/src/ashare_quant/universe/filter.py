"""Liquidity / listing / suspension filters and stratification."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import AppConfig, Board
from .boards import infer_board, is_st_name, is_supported_ashare, normalize_symbol


def _asof_slice(bars: pd.DataFrame, asof: pd.Timestamp, lookback: int) -> pd.DataFrame:
    hist = bars[bars["date"] <= asof]
    if hist.empty:
        return hist
    last_dates = hist["date"].drop_duplicates().sort_values()
    window = set(last_dates.tail(lookback))
    return hist[hist["date"].isin(window)]


def filter_universe(
    bars: pd.DataFrame,
    meta: pd.DataFrame,
    asof,
    cfg: AppConfig,
) -> pd.DataFrame:
    """Return eligible names with filter diagnostics. Does not attempt full-market coverage."""
    asof_ts = pd.Timestamp(asof)
    look = cfg.universe.lookback_days
    hist = _asof_slice(bars, asof_ts, look)
    if hist.empty:
        return meta.iloc[0:0].copy()

    rows: list[dict] = []
    allowed_boards = set(cfg.universe.boards)
    for symbol, g in hist.groupby("symbol", sort=False):
        if not is_supported_ashare(symbol):
            continue
        info = meta[meta["symbol"] == symbol]
        if info.empty:
            continue
        rec = info.iloc[0].to_dict()
        board = rec.get("board") or infer_board(symbol)
        if isinstance(board, str):
            try:
                board = Board(board)
            except ValueError:
                board = infer_board(symbol)
        if board not in allowed_boards:
            continue

        name = rec.get("name") or ""
        is_st = bool(rec.get("is_st")) or is_st_name(name)
        listing = pd.Timestamp(rec["listing_date"]) if rec.get("listing_date") is not None else None
        listing_days = int((asof_ts - listing).days) if listing is not None else 0

        g = g.sort_values("date")
        last = g.iloc[-1]
        n_sess = len(g)
        suspend_days = int(g["suspended"].fillna(False).astype(bool).sum()) if "suspended" in g else 0
        avg_amount = float(g["amount"].tail(min(20, n_sess)).mean()) if n_sess else 0.0
        market_cap = float(last["market_cap"]) if "market_cap" in last and pd.notna(last["market_cap"]) else 0.0
        long_suspend = bool(last.get("suspended", False)) and suspend_days >= cfg.universe.max_suspend_days

        reasons: list[str] = []
        ok = True
        if cfg.universe.exclude_st and is_st:
            ok, reasons = False, reasons + ["st"]
        if listing_days < cfg.universe.min_listing_days:
            ok, reasons = False, reasons + ["listing_days"]
        if avg_amount < cfg.universe.min_avg_amount:
            ok, reasons = False, reasons + ["liquidity"]
        if market_cap < cfg.universe.min_market_cap:
            ok, reasons = False, reasons + ["market_cap"]
        if suspend_days > cfg.universe.max_suspend_days or (cfg.universe.exclude_long_suspend and long_suspend):
            ok, reasons = False, reasons + ["suspension"]
        if bool(last.get("suspended", False)):
            ok, reasons = False, reasons + ["currently_suspended"]

        rows.append(
            {
                "symbol": normalize_symbol(symbol),
                "name": name,
                "board": board.value if isinstance(board, Board) else str(board),
                "is_st": is_st,
                "listing_date": listing.date() if listing is not None else None,
                "listing_days": listing_days,
                "avg_amount": avg_amount,
                "market_cap": market_cap,
                "suspend_days": suspend_days,
                "last_close": float(last["close"]),
                "eligible": ok,
                "reject_reasons": ",".join(reasons),
            }
        )

    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    eligible = frame[frame["eligible"]].copy()
    if eligible.empty:
        frame["selected"] = False
        return frame
    ranked = stratify_universe(eligible, cfg)
    keep = set(ranked["symbol"].head(cfg.universe.max_names))
    frame["selected"] = frame["symbol"].isin(keep) & frame["eligible"]
    frame = frame.merge(ranked[["symbol", "stratum", "stratum_rank"]], on="symbol", how="left")
    return frame.sort_values(["selected", "avg_amount"], ascending=[False, False]).reset_index(drop=True)


def stratify_universe(eligible: pd.DataFrame, cfg: AppConfig) -> pd.DataFrame:
    """Layer names by turnover / cap so the pool is diversified rather than all mega-caps."""
    out = eligible.copy()
    key = "avg_amount" if cfg.universe.stratification == "turnover" else "market_cap"
    if cfg.universe.stratification == "index":
        key = "market_cap"
    layers = max(1, int(cfg.universe.layers))
    try:
        out["stratum"] = pd.qcut(out[key].rank(method="first"), q=min(layers, len(out)), labels=False, duplicates="drop")
    except ValueError:
        out["stratum"] = 0
    out["stratum_rank"] = out.groupby("stratum")[key].rank(ascending=False, method="first")
    per_layer = max(1, cfg.universe.max_names // max(1, int(out["stratum"].nunique())))
    picked = (
        out.sort_values(["stratum", "stratum_rank"])
        .groupby("stratum", group_keys=False)
        .head(per_layer)
    )
    leftover = cfg.universe.max_names - len(picked)
    if leftover > 0:
        extra = out.loc[~out.index.isin(picked.index)].nlargest(leftover, key)
        picked = pd.concat([picked, extra], axis=0)
    return picked.sort_values(["stratum", "stratum_rank"]).reset_index(drop=True)
