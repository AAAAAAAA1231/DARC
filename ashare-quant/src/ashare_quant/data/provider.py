"""Data provider: CSV/parquet first, optional synthetic fallback."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..config import AppConfig
from ..paths import data_dir
from .schema import ensure_bars, load_bars, meta_from_bars, save_bars
from .synthetic import generate_synthetic_market


class MarketData:
    def __init__(self, bars: pd.DataFrame, meta: pd.DataFrame):
        self.bars = ensure_bars(bars)
        self.meta = meta.copy()

    def symbols(self) -> list[str]:
        return sorted(self.bars["symbol"].unique().tolist())

    def history(self, symbol: str, asof=None, lookback: int | None = None) -> pd.DataFrame:
        g = self.bars[self.bars["symbol"] == symbol]
        if asof is not None:
            g = g[g["date"] <= pd.Timestamp(asof)]
        if lookback is not None:
            g = g.tail(lookback)
        return g.copy()

    def snapshot(self, asof) -> pd.DataFrame:
        asof_ts = pd.Timestamp(asof)
        hist = self.bars[self.bars["date"] <= asof_ts]
        return hist.sort_values("date").groupby("symbol", as_index=False).tail(1)

    def sessions(self) -> list[pd.Timestamp]:
        return list(pd.to_datetime(self.bars["date"].drop_duplicates().sort_values()))

    def save(self, path: str | Path) -> Path:
        return save_bars(self.bars, path)

    @classmethod
    def from_csv(cls, path: str | Path) -> "MarketData":
        bars = load_bars(path)
        return cls(bars, meta_from_bars(bars))

    @classmethod
    def synthetic(cls, cfg: AppConfig | None = None, **kwargs) -> "MarketData":
        bars, meta = generate_synthetic_market(cfg, **kwargs)
        return cls(bars, meta)


def default_data_dir() -> Path:
    return data_dir()
