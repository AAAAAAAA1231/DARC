"""Self-review: settle predictions against later prices, compute metrics, emit a new model version."""

from __future__ import annotations

from typing import Any

import numpy as np
from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.orm import ModelPerformance, ModelReview, PredictionRecord
from backend.services.model_center import create_version, ensure_default_version, list_versions
from backend.strategies.plugins import ALL_STRATEGIES
from backend.strategies.weights import blend_performance, load_weights

logger = get_logger("review")


def _metrics(records: list[PredictionRecord]) -> dict[str, Any]:
    settled = [r for r in records if r.outcome in {"WIN", "LOSS"}]
    if not settled:
        return {
            "sample_size": 0,
            "win_rate": None,
            "profit_factor": None,
            "sharpe": None,
            "max_drawdown": None,
            "average_return": None,
            "expectancy": None,
            "precision": None,
            "recall": None,
            "calibration": None,
            "note": "No settled predictions yet. Metrics are not invented.",
        }
    wins = [r for r in settled if r.outcome == "WIN"]
    losses = [r for r in settled if r.outcome == "LOSS"]
    rets = []
    for r in settled:
        if r.actual_result and "return" in r.actual_result:
            rets.append(float(r.actual_result["return"]))
    arr = np.array(rets, dtype=float) if rets else np.array([0.0])
    win_rate = len(wins) / len(settled)
    gp = sum(x for x in rets if x > 0)
    gl = abs(sum(x for x in rets if x < 0))
    pf = (gp / gl) if gl > 0 else None
    sharpe = float(arr.mean() / arr.std()) if arr.std() > 0 else None
    equity = np.cumprod(1 + arr) if len(arr) else np.array([1.0])
    peak = np.maximum.accumulate(equity)
    dd = equity / peak - 1
    return {
        "sample_size": len(settled),
        "win_rate": win_rate,
        "profit_factor": pf,
        "sharpe": sharpe,
        "max_drawdown": float(dd.min()) if len(dd) else None,
        "average_return": float(arr.mean()) if len(arr) else None,
        "expectancy": float(arr.mean()) if len(arr) else None,
        "precision": win_rate,
        "recall": None,
        "calibration": None,
    }


def review_module(session: Session, module: str) -> dict[str, Any]:
    current = ensure_default_version(session, module)
    records = session.query(PredictionRecord).filter(PredictionRecord.module == module).all()
    metrics = _metrics(records)
    by_strategy: dict[str, dict[str, Any]] = {}
    for plugin in ALL_STRATEGIES:
        subset = [
            r
            for r in records
            if r.payload and any(s.get("name") == plugin.name and s.get("signal") in {"BUY", "SELL"} for s in (r.payload.get("strategy_breakdown") or []))
        ]
        by_strategy[plugin.name] = _metrics(subset) | {"note": "subset where plugin agreed with a directional call"}

    session.add(ModelPerformance(version=current.version, module=module, metrics=metrics, sample_size=metrics["sample_size"]))
    session.add(
        ModelReview(
            version=current.version,
            module=module,
            summary={
                "correct": metrics.get("win_rate"),
                "sample_size": metrics.get("sample_size"),
                "errors": "See strategy_breakdown. Causes are attributed only when settled outcomes exist.",
            },
            strategy_breakdown=by_strategy,
        )
    )
    weights = load_weights(session, module)
    hist = {name: (by_strategy[name].get("win_rate") or 0.5) for name in by_strategy}
    blended = blend_performance(weights.weights, hist, hist, hist)
    if metrics["sample_size"] >= 30:
        new_v = create_version(
            session,
            module,
            blended,
            parent=current.version,
            parameters={"kind": "self_review_blend", "min_samples": 30},
            performance=metrics,
        )
        new_version = new_v.version
    else:
        new_version = None
    logger.info("review module=%s samples=%s new=%s", module, metrics["sample_size"], new_version)
    return {
        "module": module,
        "current_version": current.version,
        "new_version": new_version,
        "metrics": metrics,
        "strategy_breakdown": by_strategy,
        "versions": [{"version": v.version, "active": v.active, "created_at": v.created_at.isoformat()} for v in list_versions(session, module)],
        "note": "Weights update only after 30 settled outcomes to reduce overfitting. Old versions remain queryable.",
    }
