"""Unified project identity, dedup, status, notes, and history. Status never deletes rows."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.core.enums import HIDDEN_PROJECT_STATUSES, ProjectStatus
from backend.core.identity import ProjectIdentity, build_project_identity
from backend.core.logging import get_logger
from backend.core.parsing import utcnow
from backend.database.orm import (
    MajorChangeAlert,
    Project,
    ProjectNote,
    ProjectSource,
    ProjectStatusHistory,
    ScoreHistory,
    UserAction,
)

logger = get_logger("projects")


def upsert_project(
    session: Session,
    identity: ProjectIdentity,
    *,
    module: str,
    symbol: str | None = None,
    narrative: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Project:
    row = session.query(Project).filter(Project.dedup_key == identity.dedup_key).one_or_none()
    if row is None:
        row = session.query(Project).filter(Project.project_id == identity.project_id).one_or_none()
    if row is None:
        row = Project(
            project_id=identity.project_id,
            dedup_key=identity.dedup_key,
            name=identity.name,
            chain=identity.chain,
            contract=identity.contract,
            website=identity.website,
            twitter=identity.twitter,
            symbol=symbol,
            narrative=narrative,
            identity_kind=identity.identity_kind,
            status=ProjectStatus.PENDING.value,
            hidden=False,
            extra=extra or {},
        )
        session.add(row)
        session.add(
            ProjectStatusHistory(
                project_id=identity.project_id,
                from_status=None,
                to_status=ProjectStatus.PENDING.value,
                reason="discovered",
                actor="system",
            )
        )
        session.flush()
        logger.info("project_created id=%s module=%s", identity.project_id, module)
    else:
        if symbol:
            row.symbol = symbol
        if narrative:
            row.narrative = narrative
        if extra:
            merged = dict(row.extra or {})
            merged.update(extra)
            row.extra = merged
        row.updated_at = utcnow()
    existing_source = (
        session.query(ProjectSource)
        .filter(ProjectSource.project_id == row.project_id, ProjectSource.module == module)
        .one_or_none()
    )
    if existing_source is None:
        session.add(ProjectSource(project_id=row.project_id, module=module, payload=extra))
    return row


def set_status(session: Session, project_id: str, status: ProjectStatus, *, reason: str | None = None, actor: str = "user") -> Project:
    row = session.query(Project).filter(Project.project_id == project_id).one()
    previous = row.status
    row.status = status.value
    row.hidden = status in HIDDEN_PROJECT_STATUSES
    row.updated_at = utcnow()
    session.add(
        ProjectStatusHistory(
            project_id=project_id,
            from_status=previous,
            to_status=status.value,
            reason=reason,
            actor=actor,
        )
    )
    session.add(UserAction(action="set_status", project_id=project_id, payload={"to": status.value, "reason": reason}))
    return row


def add_note(session: Session, project_id: str, body: str) -> ProjectNote:
    note = ProjectNote(project_id=project_id, body=body)
    session.add(note)
    session.add(UserAction(action="note", project_id=project_id, payload={"body": body[:500]}))
    return note


def record_score(session: Session, project_id: str, module: str, model_version: str, scores: dict, signal: str | None, explanation: dict | None) -> None:
    session.add(
        ScoreHistory(
            project_id=project_id,
            module=module,
            model_version=model_version,
            scores=scores,
            signal=signal,
            explanation=explanation,
        )
    )
    project = session.query(Project).filter(Project.project_id == project_id).one_or_none()
    if project:
        project.last_score = scores.get("score_50x") or scores.get("score")
        project.last_signal = signal
        if scores.get("security_verdict"):
            project.last_security = scores.get("security_verdict")


def visible_filter(query, include_hidden: bool = False):
    if include_hidden:
        return query
    return query.filter(Project.hidden.is_(False))


def project_detail(session: Session, project_id: str) -> dict[str, Any] | None:
    project = session.query(Project).filter(Project.project_id == project_id).one_or_none()
    if project is None:
        return None
    sources = session.query(ProjectSource).filter(ProjectSource.project_id == project_id).all()
    history = (
        session.query(ProjectStatusHistory)
        .filter(ProjectStatusHistory.project_id == project_id)
        .order_by(ProjectStatusHistory.created_at.asc())
        .all()
    )
    notes = session.query(ProjectNote).filter(ProjectNote.project_id == project_id).order_by(ProjectNote.created_at.desc()).all()
    scores = (
        session.query(ScoreHistory)
        .filter(ScoreHistory.project_id == project_id)
        .order_by(ScoreHistory.created_at.desc())
        .limit(50)
        .all()
    )
    alerts = session.query(MajorChangeAlert).filter(MajorChangeAlert.project_id == project_id).all()
    return {
        "project_id": project.project_id,
        "name": project.name,
        "symbol": project.symbol,
        "chain": project.chain,
        "contract": project.contract,
        "website": project.website,
        "twitter": project.twitter,
        "narrative": project.narrative,
        "status": project.status,
        "hidden": project.hidden,
        "first_seen_at": project.first_seen_at.isoformat() if project.first_seen_at else None,
        "created_at": project.created_at.isoformat() if project.created_at else None,
        "last_score": float(project.last_score) if project.last_score is not None else None,
        "last_security": project.last_security,
        "last_signal": project.last_signal,
        "sources": [s.module for s in sources],
        "status_history": [
            {
                "from": h.from_status,
                "to": h.to_status,
                "reason": h.reason,
                "actor": h.actor,
                "at": h.created_at.isoformat(),
            }
            for h in history
        ],
        "notes": [{"body": n.body, "at": n.created_at.isoformat()} for n in notes],
        "score_history": [
            {
                "module": sc.module,
                "model_version": sc.model_version,
                "scores": sc.scores,
                "signal": sc.signal,
                "explanation": sc.explanation,
                "at": sc.created_at.isoformat(),
            }
            for sc in scores
        ],
        "major_change_alerts": [
            {
                "id": a.id,
                "type": a.change_type,
                "detail": a.detail,
                "resolved": a.resolved,
                "resolution": a.resolution,
            }
            for a in alerts
        ],
        "extra": project.extra,
    }


def resolve_major_change(session: Session, alert_id: int, resolution: str) -> MajorChangeAlert:
    alert = session.query(MajorChangeAlert).filter(MajorChangeAlert.id == alert_id).one()
    alert.resolved = True
    alert.resolution = resolution
    if resolution == "reopen":
        set_status(session, alert.project_id, ProjectStatus.FOLLOWING, reason="major_change_reopen", actor="user")
    return alert
