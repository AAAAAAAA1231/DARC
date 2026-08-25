from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = PACKAGE_DIR.parent
DATA_DIR = ROOT_DIR / "data"
CACHE_DIR = DATA_DIR / "cache"
BARS_DIR = CACHE_DIR / "bars"
WEB_DIR = ROOT_DIR / "web"

UNIVERSE_PATH = DATA_DIR / "universe.json"
CALIBRATION_PATH = DATA_DIR / "calibration.json"
PREDICTIONS_PATH = DATA_DIR / "predictions.json"
SIM_PROGRESS_PATH = CACHE_DIR / "sim_progress.json"

SINA_COUNT_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/"
    "json_v2.php/Market_Center.getHQNodeStockCount?node=hs_a"
)
SINA_LIST_URL = (
    "https://vip.stock.finance.sina.com.cn/quotes_service/api/"
    "json_v2.php/Market_Center.getHQNodeData"
)
TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

HORIZON_DAYS = 5
HISTORY_BARS = 320
MIN_BARS = 80
N_SIMS_DELIVERY = 10_000_000_000
SIM_BATCH = 1_000_000
COST_BPS = 8.0  # round-trip commission + stamp duty approximation
LOOKBACK_FOR_IC = 120
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8765

for _path in (DATA_DIR, CACHE_DIR, BARS_DIR):
    _path.mkdir(parents=True, exist_ok=True)
