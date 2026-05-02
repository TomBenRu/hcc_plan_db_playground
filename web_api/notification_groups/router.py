"""Disponenten-UI: Verwaltung von Notification-Groups (Reminder) unter
`/dispatcher/notification-groups`.

Phase D: nur Lese-Endpoints (Liste der Groups + Orphan-PPs pro Team).
Mutationen (Create, Rename, Deadline-Edit, Aufloesen, Catchup, PP-Move)
kommen in Phase E + F.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session

from database import db_services, schemas
from web_api.auth.dependencies import require_role
from web_api.dependencies import get_db_session
from web_api.dispatcher.service import get_teams_for_dispatcher
from web_api.models.web_models import WebUser, WebUserRole
from web_api.notification_groups.service import (
    list_groups_for_team,
    list_orphan_pps,
)
from web_api.templating import templates


router = APIRouter(
    prefix="/dispatcher/notification-groups",
    tags=["dispatcher-notification-groups"],
)


def _get_active_team_or_404(team_id: uuid.UUID) -> schemas.TeamShow:
    """Lädt das Team, gibt 404 zurück wenn es nicht existiert oder soft-deleted ist."""
    try:
        return db_services.Team.get(team_id)
    except NoResultFound:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=f"Team {team_id} nicht gefunden oder gelöscht.",
        )


def _resolve_team_choices(session: Session, user: WebUser):
    """Teams, die in der Sidebar als Filter zur Auswahl stehen."""
    if not user.person_id:
        return []
    return get_teams_for_dispatcher(session, user.person_id)


def _build_view_context(
    request: Request,
    user: WebUser,
    session: Session,
    team_id: uuid.UUID | None,
) -> dict:
    """Bündelt die Daten fuer index.html und list-partial — eine Quelle."""
    teams = _resolve_team_choices(session, user)
    if team_id is not None:
        _get_active_team_or_404(team_id)
        selected_team_id = team_id
    elif teams:
        selected_team_id = teams[0].id
    else:
        selected_team_id = None

    if selected_team_id:
        groups = list_groups_for_team(session, selected_team_id)
        orphans = list_orphan_pps(session, selected_team_id)
    else:
        groups = []
        orphans = []

    return {
        "request": request,
        "user": user,
        "teams": teams,
        "selected_team_id": selected_team_id,
        "groups": groups,
        "orphans": orphans,
    }


@router.get("", response_class=HTMLResponse)
def index(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = None,
):
    """Hauptseite: Sidebar (Team-Filter) + Main mit Group-Cards + Orphan-Sektion."""
    ctx = _build_view_context(request, user, session, team_id)
    return templates.TemplateResponse(
        "notification_groups/index.html", ctx,
    )


@router.get("/list", response_class=HTMLResponse)
def list_partial(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = None,
):
    """HTMX-Partial — wird nach Mutationen via `notification-groups-changed`
    Event re-fetched. Phase D-Stand: Re-Fetch mangels Mutations noch ohne
    Trigger, aber das Partial existiert bereits fuer Phase E."""
    ctx = _build_view_context(request, user, session, team_id)
    return templates.TemplateResponse(
        "notification_groups/_list.html", ctx,
    )
