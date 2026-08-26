"""OHLCV schema helpers and CSV/parquet persistence."""

from __future__ import annotations

import csv
from pathlib import Path

import pandas as pd

from ..universe.boards import normalize_symbol

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


def coerce_symbol_series(values) -> pd.Series:
    s = pd.Series(values, dtype="object")
    out = []
    for raw in s.tolist():
        if raw is None or (isinstance(raw, float) and pd.isna(raw)):
            out.append("")
            continue
        text = str(raw).strip()
        if text in {"", "nan", "None", "<NA>"}:
            out.append("")
            continue
        out.append(normalize_symbol(text))
    return pd.Series(out, index=s.index, dtype="object")


def name_for_symbol(meta: pd.DataFrame, symbol: str, fallback: str = "") -> str:
    if meta is None or meta.empty or "symbol" not in meta.columns:
        return str(fallback or "")
    code = normalize_symbol(symbol)
    names = meta.loc[coerce_symbol_series(meta["symbol"]) == code, "name"]
    if names.empty:
        return str(fallback or "")
    return str(names.iloc[0] or fallback or "")


def ensure_bars(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["date"] = pd.to_datetime(out["date"]).dt.normalize()
    out["symbol"] = coerce_symbol_series(out["symbol"])
    for col in ("open", "high", "low", "close", "volume", "amount", "market_cap"):
        if col in out:
            out[col] = pd.to_numeric(out[col], errors="coerce")
    if "suspended" in out:
        out["suspended"] = out["suspended"].astype(bool)
    else:
        out["suspended"] = False
    if "name" in out.columns:
        out["name"] = out["name"].astype(str)
    return out.sort_values(["symbol", "date"]).reset_index(drop=True)


def save_bars(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if "symbol" in out.columns:
        out["symbol"] = coerce_symbol_series(out["symbol"])
    if path.suffix == ".parquet":
        out.to_parquet(path, index=False)
    else:
        out.to_csv(path, index=False, quoting=csv.QUOTE_NONNUMERIC)
    return path


def load_bars(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix == ".parquet":
        df = pd.read_parquet(path)
    else:
        df = pd.read_csv(path, dtype={"symbol": str})
    return ensure_bars(df)


def read_symbol_csv(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    df = pd.read_csv(path, dtype={"symbol": str})
    if "symbol" in df.columns:
        df["symbol"] = coerce_symbol_series(df["symbol"])
    return df


def write_symbol_csv(df: pd.DataFrame, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df.copy()
    if "symbol" in out.columns:
        out["symbol"] = coerce_symbol_series(out["symbol"])
    out.to_csv(path, index=False, quoting=csv.QUOTE_NONNUMERIC)
    return path


def meta_from_bars(bars: pd.DataFrame) -> pd.DataFrame:
    last = bars.sort_values("date").groupby("symbol", as_index=False).tail(1)
    cols = [c for c in META_COLUMNS if c in last.columns]
    meta = last[cols].reset_index(drop=True)
    if "symbol" in meta.columns:
        meta["symbol"] = coerce_symbol_series(meta["symbol"])
    return meta
