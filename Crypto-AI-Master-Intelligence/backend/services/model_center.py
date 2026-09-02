"""Immutable model versions. Updates create a new version; rollback reactivates an old one."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.orm import ModelVersion, ModelWeight
from backend.strategies.plugins import ALL_STRATEGIES

logger = get_logger("model_center")


def next_version_name(module: str, when: datetime | None = None) -> str:
    stamp = (when or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return f"model_{module.lower()}_{stamp}_{int((when or datetime.now(timezone.utc)).timestamp()) % 1000:03d}"


def ensure_default_version(session: Session, module: str) -> ModelVersion:
    existing = (
        session.query(ModelVersion)
        .filter(ModelVersion.module == module, ModelVersion.active.is_(True))
        .first()
    )
    if existing:
        return existing
    version_name = next_version_name(module)
    row = ModelVersion(
        version=version_name,
        module=module,
        parameters={"kind": "initial", "regularization": 0.05, "min_weight": 0.02, "max_weight": 0.18},
        dataset=None,
        backtest=None,
        performance=None,
        parent_version=None,
        active=True,
    )
    session.add(row)
    for plugin in ALL_STRATEGIES:
        session.add(
            ModelWeight(
                version=version_name,
                strategy=plugin.name,
                weight=plugin.initial_weight,
                min_weight=plugin.min_weight,
                max_weight=plugin.max_weight,
            )
        )
    session.flush()
    logger.info("model_version_created version=%s module=%s", version_name, module)
    return row


def create_version(
    session: Session,
    module: str,
    weights: dict[str, float],
    *,
    parent: str | None,
    parameters: dict,
    backtest: dict | None = None,
    performance: dict | None = None,
    dataset: str | None = None,
) -> ModelVersion:
    session.query(ModelVersion).filter(ModelVersion.module == module).update({"active": False})
    name = next_version_name(module)
    row = ModelVersion(
        version=name,
        module=module,
        parameters=parameters,
        dataset=dataset,
        backtest=backtest,
        performance=performance,
        parent_version=parent,
        active=True,
    )
    session.add(row)
    for plugin in ALL_STRATEGIES:
        w = weights.get(plugin.name, plugin.initial_weight)
        session.add(
            ModelWeight(
                version=name,
                strategy=plugin.name,
                weight=w,
                min_weight=plugin.min_weight,
                max_weight=plugin.max_weight,
            )
        )
    session.flush()
    return row


def rollback(session: Session, module: str, version: str) -> ModelVersion:
    target = session.query(ModelVersion).filter(ModelVersion.version == version, ModelVersion.module == module).one()
    session.query(ModelVersion).filter(ModelVersion.module == module).update({"active": False})
    target.active = True
    session.flush()
    logger.info("model_rollback module=%s version=%s", module, version)
    return target


def list_versions(session: Session, module: str | None = None) -> list[ModelVersion]:
    q = session.query(ModelVersion)
    if module:
        q = q.filter(ModelVersion.module == module)
    return q.order_by(ModelVersion.created_at.desc()).all()
