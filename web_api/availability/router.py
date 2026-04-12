"""Availability-Router: Verfügbarkeits-Eingabe für Mitarbeiter."""

import uuid
from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from database.models import ActorPlanPeriod
from web_api.auth.dependencies import LoggedInUser
from web_api.dependencies import get_db_session
from web_api.availability import service
from web_api.templating import templates

router = APIRouter(prefix="/availability", tags=["availability"])


def _require_person(user: LoggedInUser) -> uuid.UUID:
    """Stellt sicher, dass der User mit einer Person verknüpft ist."""
    if user.person_id is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Kein Person-Eintrag mit diesem Konto verknüpft",
        )
    return user.person_id


# ── Hauptseite ────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def availability_page(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    plan_period_id: uuid.UUID | None = Query(default=None),
    team_id: uuid.UUID | None = Query(default=None),
):
    person_id = _require_person(user)
    teams = service.get_teams_for_person(session, person_id)

    # Team ableiten: aus Query-Param oder erstes Team
    selected_team_id = team_id
    if selected_team_id is None and teams:
        selected_team_id = teams[0].team_id

    open_periods = service.get_open_plan_periods_for_person(
        session, person_id, team_id=selected_team_id
    )

    if not open_periods:
        return templates.TemplateResponse(
            "availability/empty.html",
            {"request": request, "user": user},
        )

    # Aktive Periode: aus Query-Param oder erste (neueste) des gewählten Teams
    active = next(
        (p for p in open_periods if p.plan_period_id == plan_period_id),
        open_periods[0],
    )
    view_model = service.build_availability_view(
        session, person_id, active, teams=teams, selected_team_id=selected_team_id
    )

    return templates.TemplateResponse(
        "availability/index.html",
        {
            "request": request,
            "user": user,
            "view_model": view_model,
            "open_periods": open_periods,
        },
    )


# ── FullCalendar Events JSON ──────────────────────────────────────────────────


@router.get("/events")
def availability_events(
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    actor_plan_period_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
):
    """FullCalendar ruft diesen Endpoint für den sichtbaren Datumsbereich auf."""
    person_id = _require_person(user)
    service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    markers = service.get_markers_for_range(session, actor_plan_period_id, start, end)

    return [
        {
            "id": str(m.avail_day_id),
            "title": m.time_of_day_enum_abbreviation,
            "start": m.day.isoformat(),
            "allDay": True,
            "color": _enum_color(m.time_of_day_enum_time_index),
            "extendedProps": {
                "time_of_day_id": str(m.time_of_day_id),
                "has_appointment": m.has_appointment,
                "enum_name": m.time_of_day_enum_name,
                "tod_start": m.time_of_day_start.strftime("%H:%M"),
                "tod_end": m.time_of_day_end.strftime("%H:%M"),
            },
        }
        for m in markers
    ]


def _enum_color(time_index: int) -> str:
    """Deterministisch: gleicher Enum-Index → gleiche Farbe."""
    palette = [
        "#F97316",  # orange (Brand) — erster Enum
        "#38BDF8",  # sky
        "#2DD4BF",  # teal
        "#818CF8",  # indigo
        "#F472B6",  # pink
        "#4ADE80",  # grün
    ]
    return palette[time_index % len(palette)]


# ── Wochen-Grid ──────────────────────────────────────────────────────────────


@router.get("/week-grid", response_class=HTMLResponse)
def week_grid(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    actor_plan_period_id: uuid.UUID = Query(...),
    start: date = Query(...),  # Montag der Woche
):
    """Serverseitig gerendertes Wochen-Grid für HTMX-Einbindung."""
    person_id = _require_person(user)
    app = service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    period_start = app.plan_period.start
    period_end = app.plan_period.end
    week_end = start + timedelta(days=6)
    markers = service.get_markers_for_range(session, actor_plan_period_id, start, week_end)

    # Tage-Map: date → Liste von Markern (Mon–Son sortiert)
    days_list: list[tuple[date, list[service.AvailDayMarker]]] = []
    for i in range(7):
        d = start + timedelta(days=i)
        days_list.append((d, []))
    marker_by_day: dict[date, list[service.AvailDayMarker]] = {d: lst for d, lst in days_list}
    for m in markers:
        if m.day in marker_by_day:
            marker_by_day[m.day].append(m)

    return templates.TemplateResponse(
        "availability/partials/week_grid.html",
        {
            "request": request,
            "days_list": days_list,
            "actor_plan_period_id": actor_plan_period_id,
            "today": date.today(),
            "palette": ["#F97316", "#38BDF8", "#2DD4BF", "#818CF8", "#F472B6", "#4ADE80"],
            "period_start": period_start,
            "period_end": period_end,
        },
    )


# ── Day-Panel ────────────────────────────────────────────────────────────────


@router.get("/day/{day}", response_class=HTMLResponse)
def day_panel(
    request: Request,
    day: date,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    actor_plan_period_id: uuid.UUID = Query(...),
):
    person_id = _require_person(user)
    app = service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    pp = app.plan_period
    is_locked = pp.closed or date.today() > pp.deadline
    detail = service.get_day_detail(
        session, actor_plan_period_id, person_id, day, is_locked,
    )
    return templates.TemplateResponse(
        "availability/partials/day_panel.html",
        {"request": request, "detail": detail},
    )


# ── AvailDay Mutations ────────────────────────────────────────────────────────


@router.post("/avail-day", response_class=HTMLResponse)
def create_avail_day(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    actor_plan_period_id: uuid.UUID = Form(...),
    day: date = Form(...),
    time_of_day_id: uuid.UUID = Form(...),
):
    person_id = _require_person(user)
    app = service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    service.check_deadline_or_403(app.plan_period)

    if service.find_avail_day(session, actor_plan_period_id, day, time_of_day_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Verfügbarkeitstag existiert bereits")

    service.create_avail_day(session, actor_plan_period_id, day, time_of_day_id)

    is_locked = _build_is_locked(app)
    detail = service.get_day_detail(session, actor_plan_period_id, person_id, day, is_locked)
    return templates.TemplateResponse(
        "availability/partials/day_panel.html",
        {"request": request, "detail": detail},
    )


@router.delete("/avail-day/{avail_day_id}", response_class=HTMLResponse)
def delete_avail_day(
    request: Request,
    avail_day_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    person_id = _require_person(user)
    ad = service.authorize_avail_day(session, person_id, avail_day_id)
    app = session.get(ActorPlanPeriod, ad.actor_plan_period_id)
    service.check_deadline_or_403(app.plan_period)

    if service.has_appointment(session, avail_day_id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Verfügbarkeitstag ist bereits eingeplant")

    day = ad.date
    actor_plan_period_id = ad.actor_plan_period_id
    service.delete_avail_day(session, avail_day_id)

    is_locked = _build_is_locked(app)
    detail = service.get_day_detail(session, actor_plan_period_id, person_id, day, is_locked)
    return templates.TemplateResponse(
        "availability/partials/day_panel.html",
        {"request": request, "detail": detail},
    )


# ── ActorPlanPeriod Update (Notes + Wunscheinsätze) ──────────────────────────


@router.patch("/actor-plan-period/{actor_plan_period_id}", response_class=HTMLResponse)
def update_actor_plan_period(
    request: Request,
    actor_plan_period_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    notes: str | None = Form(default=None),
    requested_assignments: int | None = Form(default=None),
):
    person_id = _require_person(user)
    app = service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    service.check_deadline_or_403(app.plan_period)

    if notes is not None:
        service.update_notes(session, app, notes)
    if requested_assignments is not None:
        service.update_requested_assignments(session, app, requested_assignments)

    stats = service.get_sidebar_stats(session, actor_plan_period_id, app.requested_assignments)
    return templates.TemplateResponse(
        "availability/partials/sidebar_period_stats.html",
        {"request": request, "stats": stats},
    )


# ── Meine Tageszeiten ─────────────────────────────────────────────────────────


@router.get("/time-of-days", response_class=HTMLResponse)
def time_of_days_page(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    person_id = _require_person(user)
    all_tods = service.get_person_time_of_days(session, person_id)

    # Gruppieren nach Enum (Python-seitig)
    grouped: dict[uuid.UUID, dict] = {}
    for tod in all_tods:
        if tod.enum_id not in grouped:
            grouped[tod.enum_id] = {
                "enum_id": tod.enum_id,
                "enum_name": tod.enum_name,
                "enum_abbreviation": tod.enum_abbreviation,
                "time_index": tod.enum_time_index,
                "tods": [],
            }
        grouped[tod.enum_id]["tods"].append(tod)

    enum_groups = sorted(grouped.values(), key=lambda g: g["time_index"])
    return templates.TemplateResponse(
        "availability/time_of_days.html",
        {"request": request, "user": user, "enum_groups": enum_groups},
    )


@router.post("/time-of-days", response_class=HTMLResponse)
def create_time_of_day(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    time_of_day_enum_id: uuid.UUID = Form(...),
    start: time = Form(...),
    end: time = Form(...),
    name: str = Form(default=""),
):
    person_id = _require_person(user)
    tod = service.create_person_time_of_day(session, person_id, time_of_day_enum_id, start, end, name)
    tod_info = service.get_person_time_of_days(session, person_id)
    new_info = next((t for t in tod_info if t.id == tod.id), None)
    return templates.TemplateResponse(
        "availability/partials/time_of_day_row.html",
        {"request": request, "tod": new_info},
    )


@router.patch("/time-of-days/{old_id}", response_class=HTMLResponse)
def edit_time_of_day(
    request: Request,
    old_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    start: time = Form(...),
    end: time = Form(...),
):
    person_id = _require_person(user)
    old = service.authorize_person_time_of_day(session, person_id, old_id)
    new_tod = service.replace_person_time_of_day(session, person_id, old, start, end)
    tod_info = service.get_person_time_of_days(session, person_id)
    new_info = next((t for t in tod_info if t.id == new_tod.id), None)
    return templates.TemplateResponse(
        "availability/partials/time_of_day_row.html",
        {"request": request, "tod": new_info},
    )


@router.delete("/time-of-days/{tod_id}", response_class=HTMLResponse)
def delete_time_of_day(
    tod_id: uuid.UUID,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
):
    person_id = _require_person(user)
    tod = service.authorize_person_time_of_day(session, person_id, tod_id)
    if service.count_avail_days_for_tod(session, tod_id) > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Tageszeit wird noch von Verfügbarkeitstagen genutzt",
        )
    service.remove_person_time_of_day(session, person_id, tod)
    return HTMLResponse("")  # hx-swap=outerHTML → Zeile verschwindet


# ── Hilfsfunktion ─────────────────────────────────────────────────────────────


def _build_is_locked(app: service.ActorPlanPeriod) -> bool:
    """Deadline/Closed-Check für einen ActorPlanPeriod (nach Laden von plan_period)."""
    pp = app.plan_period
    return pp.closed or date.today() > pp.deadline
