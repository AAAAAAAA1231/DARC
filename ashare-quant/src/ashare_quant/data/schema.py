"""OHLCV schema helpers and CSV/parquet persistence."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

BAR_COLUMNS = [
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "amount",
    "market_cap",
    "float_shares",
    "suspended",
    "limit_status",
    "board",
    "name",
    "listing_date",
    "is_st",
    "benchmark_close",
]

META_COLUMNS = ["symbol", "name", "board", "listing_date", "is_st", "float_shares"]


def ensure_bars(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["symbol"] = out["symbol"].astype(str).str.zfill(6)
    for col in ("open", "high", "low", "close", "volume", "amount", "market_cap"):
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "suspended" in out:
        out["suspended"] = out["suspended"].astype(bool)
    else:
        out["suspended"] = False
    return out.sort_values(["symbol", "date"]).reset_index(drop=True)


def save_bars(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        df.to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)
    return path


def load_bars(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path)
    return ensure_bars(df)


def meta_from_bars(bars: pd.DataFrame) -> pd.DataFrame:
    last = bars.sort_values("date").groupby("symbol", as_index=False).tail(1)
    cols = [c for c in META_COLUMNS if c in last.columns]
    return last[cols].reset_index(drop=True)
