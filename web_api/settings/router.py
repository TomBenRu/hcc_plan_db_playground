"""Router: Einstellungs-Endpoints (Absagefrist pro Projekt / Team)."""

import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select as sa_select
from sqlmodel import Session

from web_api.auth.dependencies import WebUserRole, require_role
from web_api.dependencies import get_db_session
from web_api.models.web_models import ProjectSettings, WebUser
from web_api.settings.service import (
    get_effective_deadline,
    upsert_project_settings,
    upsert_team_settings,
)

router = APIRouter(prefix="/settings", tags=["settings"])

AdminUser = require_role(WebUserRole.admin)
DispatcherUser = require_role(WebUserRole.dispatcher, WebUserRole.admin)


@router.get("/project/{project_id}")
def get_project_settings(
    project_id: uuid.UUID,
    user: WebUser = AdminUser,
    session: Session = Depends(get_db_session),
):
    setting = session.exec(
        sa_select(ProjectSettings).where(ProjectSettings.project_id == project_id)
    ).first()
    return {
        "project_id": str(project_id),
        "cancellation_deadline_hours": setting.cancellation_deadline_hours if setting else 48,
    }


@router.put("/project/{project_id}")
def put_project_settings(
    project_id: uuid.UUID,
    cancellation_deadline_hours: int,
    user: WebUser = AdminUser,
    session: Session = Depends(get_db_session),
):
    setting = upsert_project_settings(session, project_id, cancellation_deadline_hours)
    session.commit()
    return {"project_id": str(project_id), "cancellation_deadline_hours": setting.cancellation_deadline_hours}


@router.get("/team/{team_id}")
def get_team_settings(
    team_id: uuid.UUID,
    user: WebUser = DispatcherUser,
    session: Session = Depends(get_db_session),
):
    eff = get_effective_deadline(session, team_id)
    return {
        "team_id": str(team_id),
        "effective_deadline_hours": eff.deadline_hours,
        "source": eff.source,
    }


@router.put("/team/{team_id}")
def put_team_settings(
    team_id: uuid.UUID,
    cancellation_deadline_hours: int | None = None,
    user: WebUser = DispatcherUser,
    session: Session = Depends(get_db_session),
):
    setting = upsert_team_settings(session, team_id, cancellation_deadline_hours)
    session.commit()
    return {"team_id": str(team_id), "cancellation_deadline_hours": setting.cancellation_deadline_hours}
