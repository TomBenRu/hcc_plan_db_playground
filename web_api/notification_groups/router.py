"""Disponenten-UI: Verwaltung von Notification-Groups (Reminder) unter
`/dispatcher/notification-groups`.

Phase D: Lese-Endpoints (Liste der Groups + Orphan-PPs pro Team).
Phase E: Mutationen (Create, Rename, Deadline-Edit, Aufloesen, PP-Move
ueber Drag+Drop). Phase F: Manueller Catchup-Trigger + Polish.
"""

import datetime
import json
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.exc import NoResultFound
from sqlmodel import Session

from database import db_services, models, schemas
from web_api.auth.dependencies import require_role
from web_api.dependencies import get_db_session
from web_api.dispatcher.service import get_teams_for_dispatcher
from web_api.models.web_models import WebUser, WebUserRole
from web_api.notification_groups.service import (
    list_groups_for_team,
    list_orphan_pps,
)
from web_api.scheduler.setup import get_scheduler
from web_api.scheduler.jobs import register_jobs_for_group
from web_api.templating import templates


router = APIRouter(
    prefix="/dispatcher/notification-groups",
    tags=["dispatcher-notification-groups"],
)


def _redirect_to_ng_list(team_id: uuid.UUID) -> Response:
    """HTMX-Trigger fuer Liste-Reload + Modal-Close. Spiegelt das Pattern
    aus dispatcher_periods.router._redirect_to_list."""
    return Response(
        content="",
        media_type="text/html",
        status_code=status.HTTP_200_OK,
        headers={
            "HX-Trigger": json.dumps({
                "notification-groups-changed": {"team_id": str(team_id)},
            }),
        },
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
    Event re-fetched."""
    ctx = _build_view_context(request, user, session, team_id)
    return templates.TemplateResponse(
        "notification_groups/_list.html", ctx,
    )


# ── Modale Sub-Forms (GET) ─────────────────────────────────────────────────


@router.get("/new", response_class=HTMLResponse)
def new_form(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Modal: Neue Group anlegen — fragt Deadline + optional Name ab."""
    _get_active_team_or_404(team_id)
    today = datetime.date.today()
    return templates.TemplateResponse(
        "notification_groups/_modal_new.html",
        {
            "request": request,
            "team_id": team_id,
            "min_deadline": today + datetime.timedelta(days=1),
            "default_deadline": today + datetime.timedelta(days=14),
        },
    )


@router.get("/{group_id}/edit", response_class=HTMLResponse)
def edit_form(
    request: Request,
    group_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Modal: bestehende Group bearbeiten — Name + Deadline."""
    group = session.get(models.NotificationGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Gruppe nicht gefunden.")
    today = datetime.date.today()
    return templates.TemplateResponse(
        "notification_groups/_modal_edit.html",
        {
            "request": request,
            "group": group,
            "min_deadline": today + datetime.timedelta(days=1),
        },
    )


@router.get("/{group_id}/dissolve-confirm", response_class=HTMLResponse)
def dissolve_confirm(
    request: Request,
    group_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Modal: Bestaetigung vor dem Aufloesen einer Group."""
    group = session.get(models.NotificationGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Gruppe nicht gefunden.")
    return templates.TemplateResponse(
        "notification_groups/_modal_dissolve.html",
        {
            "request": request,
            "group": group,
            "pp_count": len(group.plan_periods),
        },
    )


# ── Mutations (POST/PATCH/DELETE) ──────────────────────────────────────────


@router.post("", response_class=HTMLResponse)
def create_group(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID = Form(...),
    deadline: datetime.date = Form(...),
    name: str = Form(default=""),
):
    """Legt eine neue (leere) NotificationGroup an. Reminder-Jobs werden
    sofort registriert — sobald PPs zugeordnet werden, sind sie aktiv."""
    _get_active_team_or_404(team_id)
    today = datetime.date.today()
    if deadline <= today:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Die Deadline muss nach dem heutigen Tag liegen.",
        )
    team = session.get(models.Team, team_id)
    group = models.NotificationGroup(
        team=team, deadline=deadline, name=(name or None),
    )
    session.add(group)
    session.commit()
    session.refresh(group)

    scheduler = get_scheduler()
    if scheduler is not None:
        register_jobs_for_group(scheduler, group)

    return _redirect_to_ng_list(team_id)


@router.patch("/{group_id}", response_class=HTMLResponse)
def patch_group(
    request: Request,
    group_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    deadline: datetime.date = Form(...),
    name: str = Form(default=""),
):
    """Update von name + deadline. Bei Deadline-Aenderung werden die
    Reminder-Jobs re-registriert (idempotent via replace_existing)."""
    group = session.get(models.NotificationGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Gruppe nicht gefunden.")
    today = datetime.date.today()
    if deadline <= today:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="Die Deadline muss nach dem heutigen Tag liegen.",
        )
    deadline_changed = group.deadline != deadline
    group.deadline = deadline
    group.name = name or None
    team_id = group.team_id
    session.commit()

    if deadline_changed:
        session.refresh(group)
        scheduler = get_scheduler()
        if scheduler is not None:
            register_jobs_for_group(scheduler, group)

    return _redirect_to_ng_list(team_id)


@router.post("/{group_id}/dissolve", response_class=HTMLResponse)
def dissolve(
    request: Request,
    group_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Loest die Gruppe auf — jede PP bekommt eine eigene 1er-Group
    (Mode 'individual'). Keine Catchup-Mails."""
    group = session.get(models.NotificationGroup, group_id)
    if group is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Gruppe nicht gefunden.")
    team_id = group.team_id
    try:
        db_services.PlanPeriod.dissolve_group(group_id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _redirect_to_ng_list(team_id)


@router.patch("/pp/{plan_period_id}/group", response_class=HTMLResponse)
def move_pp(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    group_id: str = Form(default=""),
):
    """Drag+Drop-Endpoint. `group_id` Sentinels:
      - leer ("") → unassign_group (PP wandert in "Ohne Reminder").
      - UUID     → move_to_group(uuid).

    Cross-Team-Drops werden vom Service-Layer mit ValueError abgelehnt.
    Closed PPs werden hier NICHT zusaetzlich blockiert — der Service-Layer
    laesst Group-Wechsel auch fuer geschlossene PPs zu (sie sind `closed`,
    aber strukturell intakt; Reminder-Move ist keine Strukturaenderung).
    """
    pp = session.get(models.PlanPeriod, plan_period_id)
    if pp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Periode nicht gefunden.")
    team_id = pp.team_id

    try:
        if not group_id:
            db_services.PlanPeriod.unassign_group(plan_period_id)
        else:
            try:
                target = uuid.UUID(group_id)
            except ValueError:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail=f"Ungültige group_id: {group_id!r}",
                )
            db_services.PlanPeriod.move_to_group(plan_period_id, target)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))

    return _redirect_to_ng_list(team_id)
