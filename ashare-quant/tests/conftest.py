from datetime import date

import pandas as pd
import pytest

from ashare_quant.config import AppConfig
from ashare_quant.data.synthetic import generate_synthetic_market


@pytest.fixture(scope="session")
def tiny_cfg() -> AppConfig:
    cfg = AppConfig()
    cfg.universe.min_avg_amount = 5_000_000
    cfg.universe.min_market_cap = 200_000_000
    cfg.universe.min_listing_days = 30
    cfg.universe.max_names = 16
    cfg.universe.lookback_days = 40
    cfg.risk.initial_cash = 1_000_000
    cfg.risk.max_names_held = 6
    cfg.walkforward.train_days = 80
    cfg.walkforward.test_days = 25
    cfg.walkforward.step_days = 25
    cfg.walkforward.param_grid_cap = 2
    cfg.monte_carlo.n_sims = 40
    cfg.risk.bootstrap_paths = 40
    return cfg


@pytest.fixture(scope="session")
def tiny_market(tiny_cfg):
    bars, meta = generate_synthetic_market(
        tiny_cfg,
        start=date(2024, 1, 2),
        end=date(2024, 12, 31),
        seed=7,
        n_override={"600": 4, "601": 2, "000": 3, "002": 2, "300": 3, "688": 3},
    )
    return bars, meta


@pytest.fixture(scope="session")
def asof(tiny_market):
    bars, _ = tiny_market
    return pd.to_datetime(bars["date"]).max().date()
