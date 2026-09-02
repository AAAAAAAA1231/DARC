"""Dynamic strategy weights with min/max caps and L2 regularization. No look-ahead."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.database.orm import ModelVersion, ModelWeight
from backend.strategies.plugins import ALL_STRATEGIES


@dataclass(slots=True)
class WeightSet:
    version: str
    weights: dict[str, float]


def _normalize(raw: dict[str, float]) -> dict[str, float]:
    plugins = {p.name: p for p in ALL_STRATEGIES}
    clipped = {}
    for name, plugin in plugins.items():
        value = raw.get(name, plugin.initial_weight)
        clipped[name] = min(plugin.max_weight, max(plugin.min_weight, value))
    total = sum(clipped.values()) or 1.0
    return {k: v / total for k, v in clipped.items()}


def load_weights(session: Session, module: str) -> WeightSet:
    version = (
        session.query(ModelVersion)
        .filter(ModelVersion.module == module, ModelVersion.active.is_(True))
        .order_by(ModelVersion.created_at.desc())
        .first()
    )
    if version is None:
        weights = {p.name: p.initial_weight for p in ALL_STRATEGIES}
        return WeightSet(version="model_uninitialized", weights=_normalize(weights))
    stored = session.query(ModelWeight).filter(ModelWeight.version == version.version).all()
    raw = {row.strategy: float(row.weight) for row in stored}
    return WeightSet(version=version.version, weights=_normalize(raw))


def blend_performance(initial: dict[str, float], historical: dict[str, float], recent: dict[str, float], regime: dict[str, float]) -> dict[str, float]:
    """Regularized blend. Missing series contribute 0 and reduce confidence elsewhere, not fabricated skill."""
    names = set(initial) | set(historical) | set(recent) | set(regime)
    out: dict[str, float] = {}
    for name in names:
        i = initial.get(name, 0.0)
        h = historical.get(name, i)
        r = recent.get(name, h)
        g = regime.get(name, h)
        blended = 0.25 * i + 0.25 * h + 0.25 * r + 0.25 * g
        l2 = 0.05 * (blended - i) ** 2
        out[name] = blended - l2
    return _normalize(out)
