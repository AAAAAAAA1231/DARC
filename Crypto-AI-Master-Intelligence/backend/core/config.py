"""Application settings. Secrets come from the environment only."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.paths import DATA_ROOT, PROJECT_ROOT, config_path

CONFIG_PATH = config_path()


def load_yaml_config() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {}
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("config.yaml must be a mapping")
    return data


class Settings(BaseSettings):
    app_name: str = "Crypto-AI-Master-Intelligence"
    host: str = "127.0.0.1"
    port: int = 8787
    timezone: str = "UTC"
    database_url: str = "sqlite:///./data/cami.db"
    log_level: str = "INFO"
    log_dir: str = "./logs"
    simulation_workers: int = 4
    default_paths: int = 1_000_000
    max_paths: int = 10_000_000_000
    chunk_size: int = 1_000_000
    allow_gpu: bool = True
    scheduler_enabled: bool = True
    disclaimer: str = (
        "所有输出均为统计模型结果，不是确定性预测。"
        "不是财经、投注或投资建议。"
    )

    binance_api_key: str = Field(default="", alias="BINANCE_API_KEY")
    binance_api_secret: str = Field(default="", alias="BINANCE_API_SECRET")
    coingecko_api_key: str = Field(default="", alias="COINGECKO_API_KEY")
    goplus_app_key: str = Field(default="", alias="GOPLUS_APP_KEY")
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    football_data_api_key: str = Field(default="", alias="FOOTBALL_DATA_API_KEY")
    thesportsdb_api_key: str = Field(default="3", alias="THESPORTSDB_API_KEY")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from: str = Field(default="", alias="SMTP_FROM")

    yaml_config: dict[str, Any] = Field(default_factory=dict)

    model_config = SettingsConfigDict(
        env_prefix="CAMI_",
        env_file=str(DATA_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    yaml_cfg = load_yaml_config()
    app_cfg = yaml_cfg.get("app", {})
    db_cfg = yaml_cfg.get("database", {})
    log_cfg = yaml_cfg.get("logging", {})
    sim_cfg = yaml_cfg.get("simulation", {})
    sched_cfg = yaml_cfg.get("scheduler", {})
    settings = Settings(
        app_name=app_cfg.get("name", "Crypto-AI-Master-Intelligence"),
        host=os.getenv("CAMI_HOST", app_cfg.get("host", "127.0.0.1")),
        port=int(os.getenv("CAMI_PORT", app_cfg.get("port", 8787))),
        timezone=app_cfg.get("timezone", "UTC"),
        database_url=os.getenv("CAMI_DATABASE_URL", db_cfg.get("url", "sqlite:///./data/cami.db")),
        log_level=os.getenv("CAMI_LOG_LEVEL", log_cfg.get("level", "INFO")),
        log_dir=log_cfg.get("dir", "./logs"),
        simulation_workers=int(sim_cfg.get("workers", 4)),
        default_paths=int(sim_cfg.get("default_paths", 1_000_000)),
        max_paths=int(sim_cfg.get("max_paths", 10_000_000_000)),
        chunk_size=int(sim_cfg.get("chunk_size", 1_000_000)),
        allow_gpu=bool(sim_cfg.get("allow_gpu", True)),
        scheduler_enabled=os.getenv("CAMI_SCHEDULER_ENABLED", str(sched_cfg.get("enabled", True))).lower()
        in {"1", "true", "yes"},
        disclaimer=app_cfg.get("disclaimer", Settings.model_fields["disclaimer"].default),
        yaml_config=yaml_cfg,
    )
    return settings
