from backend.core.enums import ProjectStatus
from backend.core.identity import build_project_identity
from backend.database.orm import Project
from backend.database.session import SessionLocal
from backend.services.projects import set_status, upsert_project, visible_filter


def test_hidden_status_not_deleted():
    session = SessionLocal()
    try:
        ident = build_project_identity(name="HiddenCo", website="https://hidden.example", twitter="hidden")
        row = upsert_project(session, ident, module="50X")
        pid = row.project_id
        set_status(session, pid, ProjectStatus.REJECTED, reason="user")
        session.flush()
        hidden = session.query(Project).filter(Project.project_id == pid).one()
        assert hidden.hidden is True
        visible = visible_filter(session.query(Project)).filter(Project.project_id == pid).all()
        assert visible == []
        still = session.query(Project).filter(Project.project_id == pid).all()
        assert len(still) == 1
    finally:
        session.close()
