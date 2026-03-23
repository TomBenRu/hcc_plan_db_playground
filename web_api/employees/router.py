"""Employees-Router: Mitarbeiter-Kalender."""

import uuid
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from web_api.auth.dependencies import LoggedInUser
from web_api.dependencies import get_db_session
from web_api.employees.service import (
    get_appointment_detail,
    get_appointments_for_person,
    get_coworkers_for_appointment,
    get_plan_periods_for_person,
    location_color,
)
from web_api.templating import templates

router = APIRouter(prefix="/employees", tags=["employees"])


def _require_person(user: LoggedInUser) -> uuid.UUID:
    """Stellt sicher, dass der User mit einer Person verknüpft ist."""
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknüpft",
        )
    return user.person_id


# ── Seite ─────────────────────────────────────────────────────────────────────


@router.get("/calendar", response_class=HTMLResponse)
def calendar_page(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    person_id = _require_person(user)
    plan_periods = get_plan_periods_for_person(session, person_id)

    # Initial-Datum: Start der aktuellen oder nächsten Planperiode
    today = date.today()
    initial_date = today.isoformat()
    for pp in reversed(plan_periods):  # älteste zuerst
        if pp.end >= today:
            initial_date = pp.start.isoformat()
            break

    # Alle einzigartigen Locations für die Legende
    all_events = get_appointments_for_person(session, person_id)
    seen: dict[uuid.UUID, tuple[str, str]] = {}
    for ev in all_events:
        if ev.location_id not in seen:
            seen[ev.location_id] = (ev.location_name, ev.color)
    location_legend = [
        {"name": name, "color": color}
        for name, color in seen.values()
    ]

    return templates.TemplateResponse(
        "employees/calendar.html",
        {
            "request": request,
            "user": user,
            "plan_periods": plan_periods,
            "location_legend": location_legend,
            "initial_date": initial_date,
            "total_appointments": len(all_events),
        },
    )


# ── JSON-Endpoint für FullCalendar ───────────────────────────────────────────


@router.get("/calendar/events")
def calendar_events(
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
):
    """FullCalendar ruft diesen Endpoint automatisch für den sichtbaren Datumsbereich auf."""
    person_id = _require_person(user)
    events = get_appointments_for_person(session, person_id, start, end)

    def _dt(d, t):
        """Kombiniert Datum + Zeit zu ISO-Datetime-String für FullCalendar."""
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
            },
        }
        for ev in events
    ]


# ── HTMX: Appointment-Detail ─────────────────────────────────────────────────


@router.get("/appointments/{appointment_id}", response_class=HTMLResponse)
def appointment_detail(
    request: Request,
    appointment_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    person_id = _require_person(user)
    event = get_appointment_detail(session, appointment_id, person_id)

    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    coworkers = get_coworkers_for_appointment(session, appointment_id)

    return templates.TemplateResponse(
        "employees/partials/appointment_detail.html",
        {"request": request, "event": event, "coworkers": coworkers},
    )
