from __future__ import annotations

import sys
from pathlib import Path


def _frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _candidate_roots() -> list[Path]:
    roots: list[Path] = []
    if _frozen():
        roots.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent)))
        roots.append(Path(sys.executable).resolve().parent)
    exe = Path(sys.executable).resolve()
    roots.append(exe.parent)
    roots.append(exe.parent.parent)
    roots.append(Path(__file__).resolve().parent.parent)
    return roots


def resource_root() -> Path:
    """Read-only bundled files (web UI, JSON snapshots)."""
    for root in _candidate_roots():
        has_web = (root / "web" / "index.html").exists()
        has_pred = (root / "data" / "predictions.json").exists() or (root / "predictions.json").exists()
        if has_web and has_pred:
            return root
    return Path(__file__).resolve().parent.parent


def writable_root() -> Path:
    """Writable cache next to the shipped app, or the source tree in dev."""
    if _frozen():
        return Path(sys.executable).resolve().parent
    for root in _candidate_roots():
        if (root / "web" / "index.html").exists():
            return root
    return Path(__file__).resolve().parent.parent


PACKAGE_DIR = Path(__file__).resolve().parent
ROOT_DIR = writable_root()
RESOURCE_DIR = resource_root()
DATA_DIR = RESOURCE_DIR / "data"
if not (DATA_DIR / "predictions.json").exists() and (RESOURCE_DIR / "predictions.json").exists():
    DATA_DIR = RESOURCE_DIR
CACHE_DIR = writable_root() / "data" / "cache"
BARS_DIR = CACHE_DIR / "bars"
WEB_DIR = RESOURCE_DIR / "web"

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
COST_BPS = 8.0
LOOKBACK_FOR_IC = 120
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765

CACHE_DIR.mkdir(parents=True, exist_ok=True)
BARS_DIR.mkdir(parents=True, exist_ok=True)
