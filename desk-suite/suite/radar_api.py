from __future__ import annotations

import threading
from datetime import timezone
from typing import Any

from radar.models import utcnow
from radar.report import render_html, render_json, render_scanning_html
from radar.scoring import score_many, summarize_venues
from radar.sources import collect_snapshots

_lock = threading.Lock()
_job: dict[str, Any] = {
    "status": "idle",
    "phase": "尚未扫描",
    "html": render_scanning_html(),
    "json": "{}",
    "error": "",
}


def status() -> dict[str, Any]:
    with _lock:
        return {
            "status": _job["status"],
            "phase": _job["phase"],
            "error": _job["error"],
        }


def current_html() -> str:
    with _lock:
        return str(_job.get("html") or render_scanning_html())


def current_json() -> str:
    with _lock:
        return str(_job.get("json") or "{}")


def _scan() -> None:
    try:
        with _lock:
            _job.update(status="running", phase="正在拉 GeckoTerminal / DexScreener…", error="")
        generated_at = utcnow().astimezone(timezone.utc)
        snapshots = collect_snapshots()
        scored = score_many(snapshots)
        venues = summarize_venues(snapshots)
        watchable = [s for s in scored if s.score.total >= 55]
        html = render_html(venues, watchable, generated_at)
        payload = render_json(venues, watchable, generated_at)
        with _lock:
            _job.update(status="done", phase="扫描完成", html=html, json=payload)
    except Exception as exc:
        with _lock:
            _job.update(status="error", error=str(exc), phase=f"失败：{exc}")


def start() -> dict[str, Any]:
    with _lock:
        if _job.get("status") == "running":
            return status()
        _job["status"] = "running"
        _job["phase"] = "正在扫描新场子和新盘…"
        _job["html"] = render_scanning_html()
        _job["error"] = ""
    threading.Thread(target=_scan, daemon=True).start()
    return status()
