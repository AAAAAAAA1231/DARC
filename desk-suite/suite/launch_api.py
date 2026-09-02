from __future__ import annotations

import asyncio
import threading
from typing import Any

from web3_radar.collectors.launch_hunt import hunt_launches

_lock = threading.Lock()
_job: dict[str, Any] = {
    "status": "idle",
    "phase": "尚未扫描",
    "items": [],
    "count": 0,
    "errors": [],
    "sources": [],
    "error": "",
    "since": "",
    "lookback_days": 30,
    "disclaimer": "",
}


def status() -> dict[str, Any]:
    with _lock:
        return dict(_job)


def _run() -> None:
    try:
        with _lock:
            _job.update(status="running", phase="正在搜 X：发射 / launch / 预售 / 新平台…", error="")
        try:
            loop = asyncio.new_event_loop()
            payload = loop.run_until_complete(hunt_launches(lookback_days=30))
        finally:
            loop.close()
        count = payload.get("count") or 0
        with _lock:
            prev_items = list(_job.get("items") or [])
            items = payload.get("items") or []
            kept = False
            if not items and prev_items:
                items = prev_items
                count = len(items)
                kept = True
            phase = (
                f"来源暂时没新帖，仍显示上次 {count} 条"
                if kept
                else f"完成，近一个月 {count} 条（机构/名人优先）"
            )
            _job.update(
                status="done",
                phase=phase,
                items=items,
                count=count,
                errors=payload.get("errors") or [],
                sources=payload.get("sources") or _job.get("sources") or [],
                since=payload.get("since") or "",
                lookback_days=payload.get("lookback_days") or 30,
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
        _job["phase"] = "正在按关键词检索近一个月打新动态…"
        _job["error"] = ""
    threading.Thread(target=_run, daemon=True).start()
    return status()
