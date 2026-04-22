"""Router: Dispatcher-Endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database.models import Appointment
from web_api.auth.dependencies import WebUserRole, require_role
from web_api.cancellations.service import get_cancellations_for_dispatcher
from web_api.config import get_settings
from web_api.dependencies import get_db_session
from web_api.dispatcher.dependencies import require_team_dispatcher_for_appointment
from web_api.dispatcher.service import (
    filter_allowed_team_ids,
    get_appointment_detail_for_dispatcher,
    get_appointments_for_teams,
    get_cast_status_for_appointment,
    get_team_availability_for_appointment,
    get_teams_for_dispatcher,
    replace_cast_for_appointment,
)
from web_api.email.service import send_emails_background
from web_api.employees.service import get_coworkers_for_appointment
from web_api.models.web_models import WebUser
from web_api.templating import templates

router = APIRouter(prefix="/dispatcher", tags=["dispatcher"])


def _require_person_id(user: WebUser) -> uuid.UUID:
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknüpft",
        )
    return user.person_id


@router.get("/swap-requests", response_class=HTMLResponse)
def dispatcher_swap_requests(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    status_filter: str | None = Query(default=None),
):
    from web_api.swap_requests.service import get_swap_requests_for_dispatcher
    swaps = get_swap_requests_for_dispatcher(session, user)
    if status_filter:
        swaps = [s for s in swaps if s.status.value == status_filter]
    return templates.TemplateResponse(
        "swap_requests/index.html",
        {
            "request": request,
            "user": user,
            "swaps": swaps,
            "is_dispatcher": True,
            "from_dispatcher": True,
            "status_filter": status_filter or "",
        },
    )


@router.get("/cancellations", response_class=HTMLResponse)
def dispatcher_cancellations(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    status_filter: str | None = None,
):
    cancellations = get_cancellations_for_dispatcher(session, user, status_filter)
    return templates.TemplateResponse(
        "dispatcher/cancellations.html",
        {
            "request": request,
            "user": user,
            "cancellations": cancellations,
            "status_filter": status_filter,
        },
    )


# ── Team-Pläne ────────────────────────────────────────────────────────────────


@router.get("/plan", response_class=HTMLResponse)
def dispatcher_plan(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    teams: list[uuid.UUID] = Query(default_factory=list),
    only_understaffed: bool = Query(default=False),
):
    person_id = _require_person_id(user)
    my_teams = get_teams_for_dispatcher(session, person_id)
    allowed_ids = [t.id for t in my_teams]
    effective_ids = filter_allowed_team_ids(teams, allowed_ids)

    # Initial-Datum: heute; FullCalendar springt bei Deep-Link via URL-State woanders hin,
    # aber das ist JS-Sache, nicht Server.
    initial_date = date.today().isoformat()

    # Location-Legende aus den tatsächlich sichtbaren Events aufbauen
    all_events = get_appointments_for_teams(
        session, effective_ids, only_understaffed=only_understaffed
    )
    seen: dict[uuid.UUID, tuple[str, str]] = {}
    for ev in all_events:
        if ev.location_id not in seen:
            seen[ev.location_id] = (ev.location_name, ev.color)
    location_legend = [
        {"name": name, "color": color}
        for name, color in seen.values()
    ]

    # Event-Source-URL: Team-IDs und Filter-Flag als Query-Params anhängen
    selected_for_url = teams if teams else []
    params: list[str] = [f"teams={tid}" for tid in selected_for_url]
    if only_understaffed:
        params.append("only_understaffed=1")
    events_url = "/dispatcher/plan/events"
    if params:
        events_url = f"{events_url}?{'&'.join(params)}"

    return templates.TemplateResponse(
        "dispatcher/plan.html",
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
def dispatcher_plan_events(
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    teams: list[uuid.UUID] = Query(default_factory=list),
    only_understaffed: bool = Query(default=False),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
):
    """FullCalendar-JSON-Endpoint mit Team- und Unterbesetzungs-Filter.

    Der Filter wirkt als Intersection: wenn `teams` gesetzt ist, werden
    nur Events der gewählten Teams geladen; wenn zusätzlich
    `only_understaffed=True` ist, davon nur die unterbesetzten.
    """
    person_id = _require_person_id(user)
    my_teams = get_teams_for_dispatcher(session, person_id)
    allowed_ids = [t.id for t in my_teams]
    effective_ids = filter_allowed_team_ids(teams, allowed_ids)

    events = get_appointments_for_teams(
        session, effective_ids, start, end,
        only_understaffed=only_understaffed,
    )

    def _dt(d: date, t) -> str:
        if t:
            return f"{d.isoformat()}T{t.strftime('%H:%M:%S')}"
        return d.isoformat()

    return [
        {
            "id": str(ev.appointment_id),
            "title": ev.location_name,
            "start": _dt(ev.event_date, ev.time_start),
            "end": _dt(ev.event_date, ev.time_end),
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
                "cast_count": ev.cast_count,
                "cast_required": ev.cast_required,
                "is_understaffed": ev.is_understaffed,
            },
        }
        for ev in events
    ]


@router.get("/plan/appointments/{appointment_id}", response_class=HTMLResponse)
def dispatcher_appointment_detail(
    request: Request,
    appointment_id: uuid.UUID,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """HTMX-Fragment: Termin-Details für die Dispatcher-Plan-Ansicht."""
    person_id = _require_person_id(user)
    my_teams = get_teams_for_dispatcher(session, person_id)
    allowed_ids = [t.id for t in my_teams]

    event = get_appointment_detail_for_dispatcher(session, appointment_id, allowed_ids)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    coworkers = get_coworkers_for_appointment(session, appointment_id)
    appointment = session.get(Appointment, appointment_id)  # für Notes-/Cast-Partial-Mutation

    return templates.TemplateResponse(
        "dispatcher/partials/appointment_detail.html",
        {
            "request": request,
            "event": event,
            "coworkers": coworkers,
            "appointment": appointment,
            "cast_count": event.cast_count,
            "cast_required": event.cast_required,
            "is_understaffed": event.is_understaffed,
        },
    )


# ── Notes-Edit ────────────────────────────────────────────────────────────────


@router.get("/plan/appointments/{appointment_id}/notes", response_class=HTMLResponse)
def dispatcher_notes_fragment(
    request: Request,
    edit: bool = Query(default=False),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
):
    """HTMX-Fragment: Notiz-Anzeige (edit=False) oder Edit-Form (edit=True)."""
    template_name = (
        "dispatcher/partials/notes_edit.html"
        if edit
        else "dispatcher/partials/notes_display.html"
    )
    return templates.TemplateResponse(
        template_name,
        {"request": request, "appointment": appointment},
    )


# ── Cast-Edit ─────────────────────────────────────────────────────────────────


@router.get("/plan/appointments/{appointment_id}/cast", response_class=HTMLResponse)
def dispatcher_cast_fragment(
    request: Request,
    edit: bool = Query(default=False),
    show_all: bool = Query(default=False),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
):
    """HTMX-Fragment: Cast-Anzeige (Display) oder Cast-Edit-Formular.

    Im Edit-Modus zeigt `show_all=True` alle Team-Mitarbeiter (inkl. nicht-
    verfügbarer als ausgegraute Einträge mit Tooltip), `show_all=False`
    nur aktuell zugeordnete und verfügbare.
    """
    if edit:
        candidates = get_team_availability_for_appointment(session, appointment.id)
        return templates.TemplateResponse(
            "dispatcher/partials/cast_edit.html",
            {
                "request": request,
                "appointment": appointment,
                "candidates": candidates,
                "show_all": show_all,
            },
        )

    # Display-Modus: Status + Mitarbeiter-Liste
    status_data = get_cast_status_for_appointment(session, appointment.id)
    coworkers = get_coworkers_for_appointment(session, appointment.id)
    return templates.TemplateResponse(
        "dispatcher/partials/cast_display.html",
        {
            "request": request,
            "appointment": appointment,
            "coworkers": coworkers,
            "cast_count": status_data["cast_count"],
            "cast_required": status_data["cast_required"],
            "is_understaffed": status_data["is_understaffed"],
        },
    )


@router.patch("/plan/appointments/{appointment_id}/avail-days", response_class=HTMLResponse)
def dispatcher_update_cast(
    request: Request,
    background_tasks: BackgroundTasks,
    person_ids: list[uuid.UUID] = Form(default_factory=list),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
    settings=Depends(get_settings),
):
    """Speichert Cast-Änderung; dispatcht Notifications; liefert Display-Fragment.

    Der Response-Header `HX-Trigger: hcc:cast-changed` sorgt dafür, dass der
    Dispatcher-Plan-Kalender nach dem Swap refetchEvents() aufruft — so
    bleibt der Event-Chip (inkl. Unterbesetzungs-Dot) konsistent.
    """
    payloads = replace_cast_for_appointment(session, appointment.id, person_ids)
    session.commit()
    if payloads:
        background_tasks.add_task(send_emails_background, payloads, settings)

    status_data = get_cast_status_for_appointment(session, appointment.id)
    coworkers = get_coworkers_for_appointment(session, appointment.id)
    response = templates.TemplateResponse(
        "dispatcher/partials/cast_display.html",
        {
            "request": request,
            "appointment": appointment,
            "coworkers": coworkers,
            "cast_count": status_data["cast_count"],
            "cast_required": status_data["cast_required"],
            "is_understaffed": status_data["is_understaffed"],
        },
    )
    response.headers["HX-Trigger"] = "hcc:cast-changed"
    return response


# ── Notes-Edit ────────────────────────────────────────────────────────────────


@router.patch("/plan/appointments/{appointment_id}/notes", response_class=HTMLResponse)
def dispatcher_update_notes(
    request: Request,
    notes: str = Form(default=""),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
):
    """Speichert Notiz-Text; gibt das aktualisierte Display-Fragment zurück.

    Leerer Text (nach strip) wird als `None` gespeichert → Notiz gilt als
    entfernt, Display-Partial rendert den „Anmerkung hinzufügen"-Button.
    """
    appointment.notes = notes.strip() or None
    session.commit()
    return templates.TemplateResponse(
        "dispatcher/partials/notes_display.html",
        {"request": request, "appointment": appointment},
    )