"""Viewer-Router: projektweiter Read-Only-Zugriff auf Einsatzplaene.

Phase 2 + 3 (MVP): Plan-Kalender + Termindetail-View. Beide Routen sind reine
GET-Endpoints — Mutations gibt es bewusst nicht. Auch der Admin landet hier,
falls er den Read-Only-View nutzen will.
"""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import WebUserRole, require_role
from web_api.common import fc_event_end_iso, fc_event_start_iso
from web_api.dependencies import get_db_session
from web_api.dispatcher.service import (
    filter_allowed_team_ids,
    get_appointment_detail_for_dispatcher,
    get_appointments_for_teams,
)
from web_api.models.web_models import WebUser
from web_api.templating import templates
from web_api.user_settings.service import get_color_overrides
from web_api.viewer.service import (
    get_all_teams_in_project,
    get_user_project_id,
)

router = APIRouter(prefix="/viewer", tags=["viewer"])


# ── Plan-Kalender ────────────────────────────────────────────────────────────


@router.get("/plan", response_class=HTMLResponse)
def viewer_plan(
    request: Request,
    user: WebUser = require_role(WebUserRole.viewer, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    teams: list[uuid.UUID] = Query(default_factory=list),
    only_understaffed: bool = Query(default=False),
):
    """Projektweite Plan-Sicht — alle Teams, Read-only."""
    project_id = get_user_project_id(session, user)
    my_teams = get_all_teams_in_project(session, project_id)
    allowed_ids = [t.id for t in my_teams]
    effective_ids = filter_allowed_team_ids(teams, allowed_ids)

    initial_date = date.today().isoformat()

    overrides = get_color_overrides(session, user.id)
    all_events = get_appointments_for_teams(
        session, effective_ids, only_understaffed=only_understaffed,
        user_overrides=overrides,
    )
    seen: dict[uuid.UUID, tuple[str, str]] = {}
    for ev in all_events:
        if ev.location_id not in seen:
            seen[ev.location_id] = (ev.location_name, ev.color)
    location_legend = [
        {"name": name, "color": color}
        for name, color in seen.values()
    ]

    selected_for_url = teams if teams else []
    params: list[str] = [f"teams={tid}" for tid in selected_for_url]
    if only_understaffed:
        params.append("only_understaffed=1")
    events_url = "/viewer/plan/events"
    if params:
        events_url = f"{events_url}?{'&'.join(params)}"

    return templates.TemplateResponse(
        "viewer/plan.html",
        {
            "request": request,
            "user": user,
            "my_teams": my_teams,
            "selected_team_ids": [str(tid) for tid in selected_for_url],
            "only_understaffed": only_understaffed,
            "location_legend": location_legend,
            "initial_date": initial_date,
            "total_appointments": len(all_events),
            "events_url": events_url,
        },
    )


@router.get("/plan/events")
def viewer_plan_events(
    user: WebUser = require_role(WebUserRole.viewer, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    teams: list[uuid.UUID] = Query(default_factory=list),
    only_understaffed: bool = Query(default=False),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
):
    """FullCalendar-JSON-Endpoint, gleiche Form wie der Dispatcher-Endpoint.

    Sicherheits-Schnitt: Trotz `teams` aus dem Query wird auf die im Projekt
    erlaubten Team-IDs verschnitten — ein Viewer in Projekt A kann auch durch
    URL-Manipulation keine Teams aus Projekt B sehen.
    """
    project_id = get_user_project_id(session, user)
    my_teams = get_all_teams_in_project(session, project_id)
    allowed_ids = [t.id for t in my_teams]
    effective_ids = filter_allowed_team_ids(teams, allowed_ids)

    overrides = get_color_overrides(session, user.id)
    events = get_appointments_for_teams(
        session, effective_ids, start, end,
        only_understaffed=only_understaffed,
        user_overrides=overrides,
    )

    return [
        {
            "id": str(ev.appointment_id),
            "title": ev.location_name,
            "start": fc_event_start_iso(ev.event_date, ev.time_start),
            "end": fc_event_end_iso(ev.event_date, ev.time_start, ev.time_end),
            "allDay": ev.time_start is None,
            "color": ev.color,
            "extendedProps": {
                "time_of_day": ev.time_of_day_name or "",
                "time_start": ev.time_start.strftime("%H:%M") if ev.time_start else "",
                "time_end": ev.time_end.strftime("%H:%M") if ev.time_end else "",
                "notes": ev.appointment_notes or "",
                "plan_period_id": str(ev.plan_period_id),
                "team_id": str(ev.team_id) if ev.team_id else "",
                "location_id": str(ev.location_id),
                "location_name": ev.location_name,
                "location_name_only": ev.location_name_only,
                "cast_count": ev.cast_count,
                "cast_required": ev.cast_required,
                "is_understaffed": ev.is_understaffed,
            },
        }
        for ev in events
    ]


# ── Termindetail (Read-Only) ─────────────────────────────────────────────────


@router.get("/plan/appointments/{appointment_id}", response_class=HTMLResponse)
def viewer_appointment_detail(
    appointment_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.viewer, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Read-Only-Termindetail.

    Project-Scope: das Appointment muss zum Projekt des Viewers gehoeren.
    Die Service-Funktion liefert None, wenn das Appointment nicht in den
    erlaubten Teams ist — daraus wird hier eine 404 (Information-Leak-Schutz).
    """
    from fastapi import HTTPException, status
    from database.models import Appointment
    from web_api.common import guest_list
    from web_api.employees.service import get_coworkers_for_appointment

    project_id = get_user_project_id(session, user)
    my_teams = get_all_teams_in_project(session, project_id)
    allowed_ids = [t.id for t in my_teams]

    overrides = get_color_overrides(session, user.id)
    event = get_appointment_detail_for_dispatcher(
        session, appointment_id, allowed_ids, user_overrides=overrides
    )
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Termin nicht gefunden")

    coworkers = get_coworkers_for_appointment(session, appointment_id)
    appointment = session.get(Appointment, appointment_id)

    return templates.TemplateResponse(
        "viewer/partials/appointment_detail.html",
        {
            "request": request,
            "event": event,
            "coworkers": coworkers,
            "appointment": appointment,
            "guests": guest_list(appointment.guests) if appointment else [],
            "cast_count": event.cast_count,
            "cast_required": event.cast_required,
            "is_understaffed": event.is_understaffed,
        },
    )