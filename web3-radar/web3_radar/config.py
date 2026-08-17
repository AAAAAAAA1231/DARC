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
    "signal_threshold": 0.18,
    "atr_sl_mult": 1.5,
    "atr_tp_mult": 2.5,
    "meme_min_liquidity_usd": 20_000,
    "meme_buyer_window_minutes": 30,
    "meme_min_unique_buyers": 8,
    "meme_min_holder_growth": 5,
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
    return merged


def save_settings(settings: dict[str, Any]) -> None:
    ensure_dirs()
    SETTINGS_PATH.write_text(json.dumps(settings, ensure_ascii=False, indent=2), encoding="utf-8")
