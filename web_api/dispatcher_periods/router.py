"""Disponenten-UI: Verwaltung von Planungsperioden unter `/dispatcher/periods`.

Spiegelt die Hauptfunktionen des Desktop-Dialogs `DlgPlanPeriodCreate` /
`DlgPlanPeriodEdit` ins Web-UI: Anlegen (atomar), Bearbeiten (Datum/Notes),
Schließen/Wiedereröffnen, Inline-Notes-Edit, Take-Over.

Routen sind ausschließlich für Disponenten/Admins zugänglich; Re-Open zusätzlich
nur für Admins. Layout-Vorbild: `web_api/templates/cancellations/index.html`.
"""

import datetime
import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from database import db_services, schemas
from database.db_services.plan_period import (
    PlanPeriodClosedError,
    PlanPeriodPermissionError,
)
from web_api.auth.dependencies import LoggedInUser, require_role
from web_api.dependencies import get_db_session
from web_api.dispatcher.service import get_teams_for_dispatcher
from web_api.models.web_models import WebUser, WebUserRole
from web_api.templating import templates


router = APIRouter(prefix="/dispatcher/periods", tags=["dispatcher-periods"])


def _is_admin(user: WebUser) -> bool:
    return user.has_any_role(WebUserRole.admin)


def _resolve_team_choices(session: Session, user: WebUser):
    """Teams, die in der Sidebar als Filter zur Auswahl stehen."""
    if not user.person_id:
        return []
    return get_teams_for_dispatcher(session, user.person_id)


def _filter_periods(periods, status_filter: str | None):
    """Status-Filter: aktiv | geschlossen | papierkorb (alle PPs sind dabei,
    Soft-Deleted werden nur bei status_filter='papierkorb' gezeigt)."""
    if status_filter == "papierkorb":
        return [p for p in periods if p.prep_delete is not None]
    active = [p for p in periods if p.prep_delete is None]
    if status_filter == "geschlossen":
        return [p for p in active if p.closed]
    if status_filter == "aktiv":
        return [p for p in active if not p.closed]
    return active


def _today() -> datetime.date:
    return datetime.date.today()


@router.get("", response_class=HTMLResponse)
def index(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    """Listenseite mit Sidebar-Team-Filter."""
    teams = _resolve_team_choices(session, user)
    selected_team_id = team_id
    if selected_team_id is None and teams:
        selected_team_id = teams[0].id
    periods = (
        db_services.PlanPeriod.get_all_from__team_minimal(selected_team_id)
        if selected_team_id else []
    )
    periods = _filter_periods(periods, status_filter)
    periods = sorted(periods, key=lambda p: p.start, reverse=True)

    return templates.TemplateResponse(
        "dispatcher/periods/index.html",
        {
            "request": request,
            "user": user,
            "teams": teams,
            "selected_team_id": selected_team_id,
            "status_filter": status_filter,
            "periods": periods,
            "is_admin": _is_admin(user),
            "today": _today(),
        },
    )


@router.get("/list", response_class=HTMLResponse)
def list_partial(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    """HTMX-Partial: nur die Liste, nach Filter-Wechsel."""
    periods = (
        db_services.PlanPeriod.get_all_from__team_minimal(team_id)
        if team_id else []
    )
    periods = _filter_periods(periods, status_filter)
    periods = sorted(periods, key=lambda p: p.start, reverse=True)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/list.html",
        {
            "request": request,
            "user": user,
            "periods": periods,
            "is_admin": _is_admin(user),
            "today": _today(),
            "status_filter": status_filter,
        },
    )


@router.get("/new", response_class=HTMLResponse)
def new_form(
    request: Request,
    team_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Modal: Anlage-Formular für eine neue Periode."""
    today = _today()
    return templates.TemplateResponse(
        "dispatcher/periods/partials/create_form.html",
        {
            "request": request,
            "team_id": team_id,
            "today": today,
            "default_start": today + datetime.timedelta(days=1),
            "default_end": today + datetime.timedelta(days=30),
            "default_deadline": today + datetime.timedelta(days=14),
        },
    )


@router.post("", response_class=HTMLResponse)
def create_with_children(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID = Form(...),
    start: datetime.date = Form(...),
    end: datetime.date = Form(...),
    deadline: datetime.date = Form(...),
    notes: str = Form(default=""),
    notes_for_employees: str = Form(default=""),
    remainder: bool = Form(default=False),
):
    """Atomarer Create-Submit. Bei Erfolg: Take-Over-Modal oder Liste-Refresh."""
    team = db_services.Team.get(team_id)
    create_schema = schemas.PlanPeriodCreate(
        start=start, end=end, deadline=deadline,
        notes=notes or None, notes_for_employees=notes_for_employees or None,
        remainder=remainder, team=team,
    )
    new_pp = db_services.PlanPeriod.create_with_children(create_schema)

    # Take-Over-Vorschau prüfen — falls Kandidaten existieren, Modal zeigen
    preview = db_services.PlanPeriod.find_takeover_candidates(new_pp.id)
    if preview.total_avail_days > 0 or preview.total_events > 0:
        return templates.TemplateResponse(
            "dispatcher/periods/partials/takeover_modal.html",
            {
                "request": request,
                "preview": preview,
                "plan_period_id": new_pp.id,
            },
            headers={"HX-Retarget": "#modal-root", "HX-Reswap": "innerHTML"},
        )

    # Sonst direkt: Liste neu laden
    return _redirect_to_list(team_id)


@router.get("/{plan_period_id}/edit", response_class=HTMLResponse)
def edit_form(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    pp = db_services.PlanPeriod.get(plan_period_id)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/edit_form.html",
        {
            "request": request,
            "pp": pp,
            "is_admin": _is_admin(user),
        },
    )


@router.patch("/{plan_period_id}", response_class=HTMLResponse)
def patch_period(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    start: datetime.date = Form(...),
    end: datetime.date = Form(...),
    deadline: datetime.date = Form(...),
    notes: str = Form(default=""),
    notes_for_employees: str = Form(default=""),
    remainder: bool = Form(default=False),
):
    current = db_services.PlanPeriod.get(plan_period_id)
    update_schema = schemas.PlanPeriod(
        id=plan_period_id,
        start=start, end=end, deadline=deadline,
        notes=notes or None, notes_for_employees=notes_for_employees or None,
        remainder=remainder, team=current.team,
        closed=current.closed,
        prep_delete=current.prep_delete,
    )
    try:
        db_services.PlanPeriod.update(update_schema)
    except PlanPeriodClosedError as e:
        return templates.TemplateResponse(
            "dispatcher/periods/partials/error.html",
            {"request": request, "message": str(e)},
            status_code=status.HTTP_409_CONFLICT,
        )
    return _redirect_to_list(current.team.id)


@router.get("/{plan_period_id}/notes-display", response_class=HTMLResponse)
def notes_display(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    pp = db_services.PlanPeriod.get(plan_period_id)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/notes_display.html",
        {"request": request, "pp": pp},
    )


@router.get("/{plan_period_id}/notes-edit", response_class=HTMLResponse)
def notes_edit(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    pp = db_services.PlanPeriod.get(plan_period_id)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/notes_edit.html",
        {"request": request, "pp": pp},
    )


@router.patch("/{plan_period_id}/notes", response_class=HTMLResponse)
def patch_notes(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    notes: str = Form(default=""),
):
    db_services.PlanPeriod.update_notes(plan_period_id, notes)
    pp = db_services.PlanPeriod.get(plan_period_id)
    return templates.TemplateResponse(
        "dispatcher/periods/partials/notes_display.html",
        {"request": request, "pp": pp},
    )


@router.post("/{plan_period_id}/close", response_class=HTMLResponse)
def close_period(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    pp = db_services.PlanPeriod.set_closed(
        plan_period_id, True, is_admin=_is_admin(user)
    )
    return _redirect_to_list(pp.team_id)


@router.post("/{plan_period_id}/reopen", response_class=HTMLResponse)
def reopen_period(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    if not _is_admin(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="Re-Open requires admin role")
    try:
        pp = db_services.PlanPeriod.set_closed(plan_period_id, False, is_admin=True)
    except PlanPeriodPermissionError as e:
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail=str(e))
    return _redirect_to_list(pp.team_id)


@router.post("/{plan_period_id}/takeover", response_class=HTMLResponse)
def execute_takeover(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    accepted: str = Form(default="no"),
):
    # team_id schlank über minimal=True holen — kein PlanPeriodShow-Bloat
    pp_min = db_services.PlanPeriod.get(plan_period_id, minimal=True)
    if accepted == "yes":
        db_services.PlanPeriod.execute_takeover(plan_period_id)
    return _redirect_to_list(pp_min.team.id)


@router.delete("/{plan_period_id}", response_class=HTMLResponse)
def delete_period(
    request: Request,
    plan_period_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
):
    try:
        deleted = db_services.PlanPeriod.delete(plan_period_id)
    except PlanPeriodClosedError as e:
        return templates.TemplateResponse(
            "dispatcher/periods/partials/error.html",
            {"request": request, "message": str(e)},
            status_code=status.HTTP_409_CONFLICT,
        )
    return _redirect_to_list(deleted.team_id)


def _redirect_to_list(team_id: uuid.UUID) -> Response:
    """HTMX-Trigger zum Liste-Reload + Modal-Close.

    Status 200 mit leerem Body (NICHT 204): bei `hx-target="#modal-root"
    hx-swap="innerHTML"` wird der Modal-Root mit "" ersetzt → Modal verschwindet.
    Bei `hx-swap="none"` (Card-Buttons) bleibt der Swap aus, nur der Trigger
    feuert. Bei 204 würde HTMX laut Spec *gar keinen* Swap ausführen, das
    Modal bliebe stehen.
    """
    return Response(
        content="",
        media_type="text/html",
        status_code=status.HTTP_200_OK,
        headers={
            "HX-Trigger": f'{{"periods-changed": {{"team_id": "{team_id}"}} }}',
        },
    )
