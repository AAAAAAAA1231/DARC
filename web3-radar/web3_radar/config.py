from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))
    return Path(__file__).resolve().parent


def _writable_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


APP_DIR = _bundle_dir()
ROOT_DIR = _writable_root()
DATA_DIR = ROOT_DIR / "data"
_STATIC_CANDIDATES = [
    Path(__file__).resolve().parent / "static",
    APP_DIR / "web3_radar" / "static",
    APP_DIR / "static",
]
STATIC_DIR = next((p for p in _STATIC_CANDIDATES if p.exists()), _STATIC_CANDIDATES[0])
DB_PATH = DATA_DIR / "radar.db"
SETTINGS_PATH = DATA_DIR / "settings.json"

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787

FAMOUS_VCS = [
    "a16z",
    "andreessen horowitz",
    "paradigm",
    "sequoia",
    "binance labs",
    "ynzi labs",
    "coinbase ventures",
    "polychain",
    "pantera",
    "multicoin",
    "dragonfly",
    "lightspeed",
    "framework",
    "hack vc",
    "variant",
    "union square ventures",
    "usv",
    "softbank",
    "animoca",
    "delphi",
    "hashed",
    "jump crypto",
    "wintermute",
    "okx ventures",
    "bybit",
    "galaxy",
    "electric capital",
    "placeholder",
    "blockchain capital",
    "coinbase",
    "circle ventures",
    "riptide",
    "spartan",
    "mechanism",
    "1kx",
    "robot ventures",
    "standard crypto",
    "founders fund",
    "tiger global",
    "temasek",
    "softbank vision",
]

INITIAL_INDICATOR_SHARES: dict[str, float] = {
    "td13": 12.0,
    "harmonic": 11.0,
    "elliott": 6.0,
    "ichimoku": 6.0,
    "macd": 6.0,
    "rsi": 6.0,
    "supertrend": 5.0,
    "ema_cross": 5.0,
    "bollinger": 4.0,
    "fibonacci": 4.0,
    "adx_dmi": 4.0,
    "stochastic": 3.5,
    "parabolic_sar": 3.5,
    "keltner": 3.0,
    "donchian": 3.0,
    "mfi": 3.0,
    "cci": 3.0,
    "williams_r": 2.5,
    "obv": 2.5,
    "cmf": 2.0,
    "vwap": 2.0,
    "awesome_oscillator": 2.0,
    "heikin_ashi": 2.0,
    "engulfing": 2.0,
    "volume_spike": 2.0,
    "roc": 1.5,
    "trix": 1.5,
    "pivot_points": 1.5,
    "ultimate_oscillator": 1.5,
    "atr_breakout": 1.5,
}

DEFAULT_SETTINGS: dict[str, Any] = {
    "host": DEFAULT_HOST,
    "port": DEFAULT_PORT,
    "kline_interval": "4h",
    "kline_limit": 500,
    "monte_carlo_sims": 1_000_000,
    "monte_carlo_top_pct": 1.0,
    "signal_threshold": 0.22,
    "atr_sl_mult": 1.8,
    "atr_tp_mult": 2.8,
    "risk_per_trade_pct": 0.5,
    "max_contract_positions": 3,
    "max_same_side_positions": 2,
    "min_trend_agreement": 0.45,
    "partial_tp_r": 1.0,
    "partial_tp_frac": 0.40,
    "breakeven_r": 1.0,
    "trail_arm_r": 1.5,
    "trail_atr_mult": 1.0,
    "meme_rules_version": 7,
    "meme_min_liquidity_usd": 100_000,
    "meme_buyer_window_minutes": 30,
    "meme_min_unique_buyers": 15,
    "meme_min_holder_growth": 8,
    "meme_max_1h_change": 20,
    "meme_max_m5_change": 22,
    "meme_min_age_minutes": 72 * 60,
    "airdrop_min_funding_usd": 20_000_000,
    "ambassador_lookback_days": 7,
    "twitter_bearer_token": "",
    "binance_api_key": "",
    "binance_api_secret": "",
    "okx_api_key": "",
    "okx_api_secret": "",
    "okx_passphrase": "",
    "auto_participate": False,
    "auto_max_spend_usd": 50,
    "auto_require_confirm": True,
    "wallet_address": "",
    "wallet_chain": "ethereum",
    "copy_enabled": True,
    "copy_mode": "paper",
    "copy_max_positions": 1,
    "copy_size_usd": 10,
    "copy_sl_pct": 0.28,
    "copy_tp_pct": 9.0,
    "copy_max_1h_change": 20,
    "copy_min_heat": 70,
    "copy_max_risk": 50,
    "copy_paper_equity": 1000,
    "copy_cooldown_minutes": 60 * 24 * 28,
    "copy_max_size_pct": 0.01,
    "copy_trail_arm_pct": 1.0,
    "copy_trail_lock_pct": 4.0,
    "copy_daily_loss_pct": 0.06,
    "copy_time_stop_minutes": 60 * 24 * 30,
    "copy_giveup_pct": 0.50,
    "copy_scale1_mult": 2.0,
    "copy_scale2_mult": 5.0,
    "copy_scale_frac": 0.35,
    "copy_scale2_frac": 0.25,
    "copy_fast_fail_minutes": 1440,
    "copy_fast_fail_pct": 0.20,
    "copy_struct_m5_fail": -25,
    "copy_struct_h1_min": 0,
    "copy_struct_h6_fail": -28,
    "copy_require_multi_source": False,
    "weight_refit_days": 7,
}


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_settings() -> dict[str, Any]:
    ensure_dirs()
    if not SETTINGS_PATH.exists():
        save_settings(DEFAULT_SETTINGS)
        return dict(DEFAULT_SETTINGS)
    raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
    merged = dict(DEFAULT_SETTINGS)
    merged.update(raw)
    merged = _apply_meme_rules_upgrade(merged)
    return merged


MEME_RULE_KEYS = (
    "meme_min_liquidity_usd",
    "meme_min_unique_buyers",
    "meme_min_holder_growth",
    "meme_max_1h_change",
    "meme_max_m5_change",
    "meme_min_age_minutes",
    "copy_sl_pct",
    "copy_tp_pct",
    "copy_max_1h_change",
    "copy_min_heat",
    "copy_max_risk",
    "copy_max_positions",
    "copy_size_usd",
    "copy_max_size_pct",
    "copy_trail_arm_pct",
    "copy_trail_lock_pct",
    "copy_daily_loss_pct",
    "copy_cooldown_minutes",
    "copy_time_stop_minutes",
    "copy_giveup_pct",
    "copy_scale1_mult",
    "copy_scale2_mult",
    "copy_scale_frac",
    "copy_scale2_frac",
    "copy_fast_fail_minutes",
    "copy_fast_fail_pct",
    "copy_struct_m5_fail",
    "copy_struct_h1_min",
    "copy_struct_h6_fail",
)


def _apply_meme_rules_upgrade(settings: dict[str, Any]) -> dict[str, Any]:
    """Force monthly meme-coin defaults over leftover scalp settings."""
    target = int(DEFAULT_SETTINGS.get("meme_rules_version") or 7)
    current = int(settings.get("meme_rules_version") or 0)
    if current >= target:
        return settings
    upgraded = dict(settings)
    for key in MEME_RULE_KEYS:
        upgraded[key] = DEFAULT_SETTINGS[key]
    upgraded["meme_rules_version"] = target
    save_settings(upgraded)
    return upgraded


def save_settings(settings: dict[str, Any]) -> None:
    ensure_dirs()
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
