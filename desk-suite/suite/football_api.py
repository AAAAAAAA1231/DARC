from __future__ import annotations

import threading
from typing import Any

from football_predictor.model.pipeline import PredictionResult, Predictor

_lock = threading.Lock()
_predictor = Predictor()
_job: dict[str, Any] = {
    "status": "idle",
    "phase": "尚未预测",
    "results": [],
    "error": "",
}


def prediction_to_dict(result: PredictionResult) -> dict[str, Any]:
    return {
        "league_cn": result.league_cn,
        "kickoff": result.kickoff,
        "home_cn": result.home_cn,
        "away_cn": result.away_cn,
        "match": f"{result.home_cn} vs {result.away_cn}",
        "pred_1x2_90": result.pred_1x2_90,
        "final_1x2": result.final_1x2,
        "final_score": result.final_score,
        "p_home": result.p_home,
        "p_draw": result.p_draw,
        "p_away": result.p_away,
        "probs": f"{result.p_home:.0%} / {result.p_draw:.0%} / {result.p_away:.0%}",
        "confidence": result.confidence,
        "factors": list(result.factors or [])[:6],
        "final_note": result.final_note,
        "weather": result.weather,
    }


def status() -> dict[str, Any]:
    with _lock:
        return dict(_job)


def _set(**kwargs: Any) -> None:
    with _lock:
        _job.update(kwargs)


def _run(kind: str, query: str = "") -> None:
    try:
        _set(status="running", error="", results=[])
        if not _predictor.ready():
            _predictor.build(progress=lambda m: _set(phase=m))
        if kind == "search":
            _set(phase=f"正在搜索「{query}」…")
            msg, results = _predictor.predict_search(query, progress=lambda m: _set(phase=m))
            _set(status="done", phase=msg, results=[prediction_to_dict(r) for r in results])
            return
        _set(phase="正在拉取近期赛程并逐场纠偏…")
        results = _predictor.predict_all_upcoming(progress=lambda m: _set(phase=m))
        _set(
            status="done",
            phase=f"完成 {len(results)} 场" if results else "没有找到近期未赛场次",
            results=[prediction_to_dict(r) for r in results],
        )
    except Exception as exc:
        _set(status="error", error=str(exc), phase=f"失败：{exc}")


def start(kind: str = "all", query: str = "") -> dict[str, Any]:
    with _lock:
        if _job.get("status") == "running":
            return dict(_job)
        _job["status"] = "running"
        _job["phase"] = "正在联网，请稍候…"
        _job["error"] = ""
    threading.Thread(target=_run, args=(kind, query), daemon=True).start()
    return status()
