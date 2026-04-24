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
    get_appointment_detail_for_team,
    get_appointments_for_person,
    get_coworkers_for_appointment,
    get_own_pending_offer_for_appointment,
    get_plan_periods_for_person,
    get_team_appointments_for_person,
)
from web_api.templating import templates
from web_api.user_settings.service import get_color_overrides

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

    # Legende aus own + team: deckt alle Orte ab, die mit dem Show-All-Toggle
    # überhaupt erscheinen können, damit sich die Legende nicht an-/abschaltet.
    overrides = get_color_overrides(session, user.id)
    own_events = get_appointments_for_person(session, person_id, user_overrides=overrides)
    team_events = get_team_appointments_for_person(session, person_id, user_overrides=overrides)
    seen: dict[uuid.UUID, tuple[str, str]] = {}
    for ev in own_events + team_events:
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
            "total_appointments": len(own_events),
        },
    )


# ── JSON-Endpoint für FullCalendar ───────────────────────────────────────────


@router.get("/calendar/events")
def calendar_events(
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    start: date | None = Query(default=None),
    end: date | None = Query(default=None),
    show_all: int = Query(default=0),
    only_understaffed: int = Query(default=0),
):
    """FullCalendar-Events mit zwei optionalen Filtern:

    - `show_all=1`: zusätzlich alle Termine in den Teams der Person (nicht nur
      die, bei denen sie eingeteilt ist). Fremde Termine sind via `is_own=false`
      in den extendedProps markiert, damit das Template sie visuell abheben kann.
    - `only_understaffed=1`: filtert unterbesetzte Termine (Intersection mit show_all).
    """
    person_id = _require_person(user)
    overrides = get_color_overrides(session, user.id)

    own_events = get_appointments_for_person(session, person_id, start, end, user_overrides=overrides)
    own_ids = {ev.appointment_id for ev in own_events}

    if show_all:
        team_events = get_team_appointments_for_person(session, person_id, start, end, user_overrides=overrides)
        # Eigene haben keinen cast_count (old query sammelt nicht) — per appointment_id
        # aus team_events anreichern, damit auch für own-Events unterbesetzt markiert
        # wird und die Definition konsistent ist.
        cast_by_id = {ev.appointment_id: ev for ev in team_events}
        merged: list = []
        for ev in own_events:
            enriched = cast_by_id.get(ev.appointment_id)
            if enriched is not None:
                ev.cast_count = enriched.cast_count
                ev.cast_required = enriched.cast_required
                ev.is_understaffed = enriched.is_understaffed
            ev.is_own = True
            merged.append(ev)
        for ev in team_events:
            if ev.appointment_id not in own_ids:
                ev.is_own = False
                merged.append(ev)
        events = merged
    else:
        # Auch im Default-Modus cast_count anreichern, damit unterbesetzt-Filter
        # konsistent wirkt.
        team_events = get_team_appointments_for_person(session, person_id, start, end, user_overrides=overrides)
        cast_by_id = {ev.appointment_id: ev for ev in team_events}
        for ev in own_events:
            enriched = cast_by_id.get(ev.appointment_id)
            if enriched is not None:
                ev.cast_count = enriched.cast_count
                ev.cast_required = enriched.cast_required
                ev.is_understaffed = enriched.is_understaffed
            ev.is_own = True
        events = own_events

    if only_understaffed:
        events = [ev for ev in events if ev.is_understaffed]

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
                "is_own": ev.is_own,
                "is_understaffed": ev.is_understaffed,
                "cast_count": ev.cast_count,
                "cast_required": ev.cast_required,
                "location_name_only": ev.location_name_only,
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
    overrides = get_color_overrides(session, user.id)
    event = get_appointment_detail(session, appointment_id, person_id, user_overrides=overrides)
    # Fallback: fremder Termin in einem Team der Person (E1-Show-All)
    if event is None:
        event = get_appointment_detail_for_team(session, appointment_id, person_id, user_overrides=overrides)

    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND)

    coworkers = get_coworkers_for_appointment(session, appointment_id)

    # Nur bei fremden unterbesetzten Terminen braucht das Template den Offer-Status —
    # sonst ist der Offer-Action-Block ohnehin nicht sichtbar.
    own_pending_offer = None
    if not event.is_own and event.is_understaffed:
        own_pending_offer = get_own_pending_offer_for_appointment(
            session, user.id, appointment_id
        )

    return templates.TemplateResponse(
        "employees/partials/appointment_detail.html",
        {
            "request": request,
            "event": event,
            "coworkers": coworkers,
            "own_pending_offer": own_pending_offer,
            "today": date.today(),
        },
    )
