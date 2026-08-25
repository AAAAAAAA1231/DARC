from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .method_catalog import METHODS

app = FastAPI(title="大A量化研判系统", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if config.WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=config.WEB_DIR), name="assets")


@lru_cache(maxsize=4)
def _load_json(path_str: str, mtime: float):
    path = Path(path_str)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _predictions() -> dict | None:
    path = config.PREDICTIONS_PATH
    if not path.exists():
        return None
    return _load_json(str(path), path.stat().st_mtime)


def _calibration() -> dict | None:
    path = config.CALIBRATION_PATH
    if not path.exists():
        return None
    return _load_json(str(path), path.stat().st_mtime)


@app.get("/")
def index():
    index_path = config.WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(500, "web/index.html missing")
    return FileResponse(index_path)


@app.get("/api/health")
def health():
    pred = _predictions()
    cal = _calibration()
    return {
        "ok": True,
        "universe": (pred or {}).get("count") or 0,
        "calibrated": cal is not None,
        "n_sims": (cal or {}).get("n_sims"),
        "disclaimer": "研究工具，不构成投资建议。",
    }


@app.get("/api/meta")
def meta():
    cal = _calibration() or {}
    pred = _predictions() or {}
    return {
        "methods": [{"name": m.name, "title": m.title, "family": m.family} for m in METHODS],
        "calibration": {
            "n_sims": cal.get("n_sims"),
            "elapsed_sec": cal.get("elapsed_sec"),
            "best_sharpe": cal.get("best_sharpe"),
            "sample_size": cal.get("sample_size"),
            "generated_at": cal.get("generated_at"),
            "methods": cal.get("methods") or [],
        },
        "predictions": {
            "count": pred.get("count") or 0,
            "generated_at": pred.get("generated_at"),
            "horizon_days": pred.get("horizon_days") or config.HORIZON_DAYS,
        },
        "disclaimer": cal.get("disclaimer") or "研究工具，不构成投资建议。",
    }


@app.get("/api/stocks")
def list_stocks(
    q: str = "",
    direction: str = "",
    board: str = "",
    page: int = Query(1, ge=1),
    page_size: int = Query(40, ge=1, le=200),
    sort: str = "score",
):
    pred = _predictions()
    if not pred:
        raise HTTPException(404, "尚未生成预测，请先运行 python -m a_share_trading run")
    items = pred["items"]
    q = q.strip().lower()
    if q:
        items = [x for x in items if q in x["code"].lower() or q in x["name"].lower() or q in x["symbol"].lower()]
    if direction:
        items = [x for x in items if x["direction"] == direction]
    if board:
        items = [x for x in items if board in x["board"]]
    reverse = True
    key = sort.lstrip("-")
    if sort.startswith("-"):
        reverse = False
    if key in {"score", "confidence", "change_pct", "last", "mktcap", "reward_risk"}:
        items = sorted(items, key=lambda x: (x.get(key) is None, x.get(key) or 0), reverse=reverse)
    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    slim = [
        {
            "code": x["code"],
            "name": x["name"],
            "board": x["board"],
            "exchange": x["exchange"],
            "last": x["last"],
            "change_pct": x["change_pct"],
            "direction": x["direction"],
            "score": x["score"],
            "confidence": x["confidence"],
            "take_profit": x["take_profit"],
            "stop_loss": x["stop_loss"],
            "side": x["side"],
            "data_source": x["data_source"],
            "reward_risk": x["reward_risk"],
        }
        for x in page_items
    ]
    up = sum(1 for x in pred["items"] if x["direction"] == "上涨")
    down = sum(1 for x in pred["items"] if x["direction"] == "下跌")
    flat = len(pred["items"]) - up - down
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {"up": up, "down": down, "flat": flat, "all": len(pred["items"])},
        "items": slim,
    }


@app.get("/api/stocks/{code}")
def stock_detail(code: str):
    pred = _predictions()
    if not pred:
        raise HTTPException(404, "尚未生成预测")
    code = code.zfill(6)
    for item in pred["items"]:
        if item["code"] == code:
            return item
    raise HTTPException(404, f"未找到 {code}")
