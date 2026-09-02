from __future__ import annotations

import asyncio
import threading
from typing import Any

from web3_radar.collectors.airdrop_recommend import recommend_airdrops

_lock = threading.Lock()
_job: dict[str, Any] = {
    "status": "idle",
    "phase": "尚未扫描",
    "items": [],
    "recommend_count": 0,
    "errors": [],
    "error": "",
    "model": "",
    "disclaimer": "",
}


def status() -> dict[str, Any]:
    with _lock:
        return dict(_job)


def _run() -> None:
    try:
        with _lock:
            _job.update(status="running", phase="正在拉融资、积分计划和历史对照…", error="")
        try:
            loop = asyncio.new_event_loop()
            payload = loop.run_until_complete(recommend_airdrops())
        finally:
            loop.close()
        with _lock:
            _job.update(
                status="done",
                phase=f"完成，推荐 {payload.get('recommend_count') or 0} 个",
                items=payload.get("items") or [],
                recommend_count=payload.get("recommend_count") or 0,
                errors=payload.get("errors") or [],
                model=payload.get("model") or "",
                disclaimer=payload.get("disclaimer") or "",
            )
    except Exception as exc:
        with _lock:
            _job.update(status="error", error=str(exc), phase=f"失败：{exc}")


def start() -> dict[str, Any]:
    with _lock:
        if _job.get("status") == "running":
            return status()
        _job["status"] = "running"
        _job["phase"] = "正在评分空投项目…"
        _job["error"] = ""
    threading.Thread(target=_run, daemon=True).start()
    return status()
