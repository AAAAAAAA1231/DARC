from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class Board(str, Enum):
    SSE_MAIN = "sse_main"
    SZSE_MAIN = "szse_main"
    CHINEXT = "chinext"
    STAR = "star"


class SignalName(str, Enum):
    TREND = "trend"
    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    VOLATILITY = "volatility"
    RELATIVE_STRENGTH = "relative_strength"


class LimitStatus(str, Enum):
    NORMAL = "normal"
    TOUCH_UP = "touch_up"
    SEALED_UP = "sealed_up"
    TOUCH_DOWN = "touch_down"
    SEALED_DOWN = "sealed_down"


class Action(str, Enum):
    BUY = "buy"
    HOLD = "hold"
    REDUCE = "reduce"
    EXIT = "exit"
    NO_TRADE = "no_trade"


class UniverseConfig(BaseModel):
    boards: list[Board] = Field(default_factory=lambda: list(Board))
    min_listing_days: int = 60
    min_avg_amount: float = 50_000_000
    min_market_cap: float = 3_000_000_000
    max_suspend_days: int = 5
    exclude_st: bool = True
    exclude_long_suspend: bool = True
    lookback_days: int = 60
    stratification: str = "turnover"
    max_names: int = 80
    layers: int = 4


class MarketConfig(BaseModel):
    lot_size: int = 100
    t_plus: int = 1
    main_limit: float = 0.10
    chinext_limit: float = 0.20
    star_limit: float = 0.20
    st_limit: float = 0.05
    ipo_no_limit_days: int = 5
    max_adv_participation: float = 0.02
    sealed_limit_fill_prob: float = 0.0
    touch_limit_fill_prob: float = 0.35


class CostConfig(BaseModel):
    commission_rate: float = 0.0003
    commission_min: float = 5.0
    stamp_tax_sell: float = 0.0005
    transfer_fee: float = 0.00001
    base_slippage: float = 0.001
    atr_slippage_k: float = 0.05


class SignalParams(BaseModel):
    lookback: int = 60
    trend: dict[str, Any] = Field(default_factory=lambda: {"fast": 12, "slow": 48, "adx_window": 14})
    momentum: dict[str, Any] = Field(default_factory=lambda: {"roc_window": 20, "rsi_window": 14})
    mean_reversion: dict[str, Any] = Field(default_factory=lambda: {"z_window": 20, "entry_z": 1.2})
    volatility: dict[str, Any] = Field(default_factory=lambda: {"atr_window": 14, "breakout_k": 1.8})
    relative_strength: dict[str, Any] = Field(default_factory=lambda: {"window": 20})
    long_threshold: float = 0.25
    exit_threshold: float = -0.10


class EnsembleConfig(BaseModel):
    oos_lookback: int = 60
    half_life: int = 20
    temperature: float = 0.75
    min_weight: float = 0.04
    max_weight: float = 0.45
    negative_sharpe_floor: float = -0.5
    methods: list[SignalName] = Field(default_factory=lambda: list(SignalName))


class RiskConfig(BaseModel):
    initial_cash: float = 1_000_000.0
    max_gross_exposure: float = 0.80
    max_single_weight: float = 0.08
    max_board_weight: float = 0.45
    per_name_risk: float = 0.008
    max_names_held: int = 12
    atr_window: int = 14
    stop_atr_k: float = 1.8
    take_atr_k: float = 2.6
    vol_adapt: bool = True
    ci_levels: list[float] = Field(default_factory=lambda: [0.10, 0.50, 0.90])
    bootstrap_paths: int = 200


class WalkForwardConfig(BaseModel):
    train_days: int = 252
    test_days: int = 63
    step_days: int = 63
    inner_validation_frac: float = 0.25
    min_folds: int = 3
    selection: str = "robust"
    param_grid_cap: int = 8


class MonteCarloConfig(BaseModel):
    n_sims: int = 120
    block_size: int = 5
    slippage_low: float = 0.6
    slippage_high: float = 2.2
    fill_jitter: float = 0.25
    dd_alert: float = 0.22
    dd_prob_cap: float = 0.20


class PaperConfig(BaseModel):
    days: int = 40
    require_confirmation: bool = True


class WebConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8765


class DataConfig(BaseModel):
    source: str = "live"  # live | synthetic
    live_scan: int = 160
    live_max_symbols: int = 80
    live_kline_begin: str = "20190101"
    timeout_sec: float = 20.0
    kline_workers: int = 6
    retries: int = 4


class AppConfig(BaseModel):
    seed: int = 42
    base_currency: str = "CNY"
    data: DataConfig = Field(default_factory=DataConfig)
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    market: MarketConfig = Field(default_factory=MarketConfig)
    costs: CostConfig = Field(default_factory=CostConfig)
    signals: SignalParams = Field(default_factory=SignalParams)
    ensemble: EnsembleConfig = Field(default_factory=EnsembleConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    walkforward: WalkForwardConfig = Field(default_factory=WalkForwardConfig)
    monte_carlo: MonteCarloConfig = Field(default_factory=MonteCarloConfig)
    paper: PaperConfig = Field(default_factory=PaperConfig)
    web: WebConfig = Field(default_factory=WebConfig)


from .paths import resolve_config_path


def load_config(path: str | Path | None = None) -> AppConfig:
    cfg_path = resolve_config_path(path)
    if not cfg_path.exists():
        return AppConfig()
    with cfg_path.open("r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh) or {}
    return AppConfig.model_validate(raw)


def parse_date(value: date | datetime | str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])
