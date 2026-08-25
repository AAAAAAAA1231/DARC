from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import os
import sys


APP_NAME = "三大联赛胜负推理"
APP_VERSION = "1.1.0"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# football-data.co.uk 赛季代码，从新到旧。当前赛季优先。
SEASONS = ["2627", "2526", "2425", "2324", "2223", "2122"]
SECOND_DIV_SEASONS = ["2526", "2425", "2324"]

# Dixon-Coles / Elo 超参
HALF_LIFE_DAYS = 160.0
DC_MAX_ITER = 70
ELO_K = 18.0
ELO_HOME_ADV = 55.0
ELO_MEAN = 1500.0
MAX_GOALS = 8
FORM_MATCHES = 8
FORM_PRIOR = 6.0  # 赛季初收缩强度
BLEND_DC = 0.62
BLEND_ELO = 0.18
BLEND_MARKET = 0.20
CALIBRATION_HOLDOUT = 120
NEWS_ADJUST_CAP = 0.22  # 单项情报对 xG 的最大乘数偏离


def app_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def user_data_dir() -> Path:
    if os.name == "nt":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    else:
        root = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    path = root / "football_predictor"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_dir() -> Path:
    path = user_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class League:
    key: str
    name_cn: str
    name_en: str
    fd_code: str  # football-data.co.uk 一级联赛文件
    fd_code_2: str  # 二级联赛，用于升班马
    espn_slug: str
    sportsdb_id: str
    teams_n: int
    typical_home_adv: float
    # 联赛风格：用于平局先验微调（意甲略高、德甲略低）
    draw_bias: float = 0.0


LEAGUES: dict[str, League] = {
    "laliga": League(
        key="laliga",
        name_cn="西甲",
        name_en="La Liga",
        fd_code="SP1",
        fd_code_2="SP2",
        espn_slug="esp.1",
        sportsdb_id="4335",
        teams_n=20,
        typical_home_adv=1.32,
        draw_bias=0.01,
    ),
    "bundesliga": League(
        key="bundesliga",
        name_cn="德甲",
        name_en="Bundesliga",
        fd_code="D1",
        fd_code_2="D2",
        espn_slug="ger.1",
        sportsdb_id="4331",
        teams_n=18,
        typical_home_adv=1.38,
        draw_bias=-0.015,
    ),
    "seriea": League(
        key="seriea",
        name_cn="意甲",
        name_en="Serie A",
        fd_code="I1",
        fd_code_2="I2",
        espn_slug="ita.1",
        sportsdb_id="4332",
        teams_n=20,
        typical_home_adv=1.30,
        draw_bias=0.02,
    ),
}

LEAGUE_ORDER = ["laliga", "bundesliga", "seriea"]
