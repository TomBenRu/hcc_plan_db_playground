"""Availability-Router: Verfügbarkeits-Eingabe für Mitarbeiter."""

import uuid
from datetime import date, time, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Query, status
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import ActorPlanPeriod, AvailDay, Person, TimeOfDay, TimeOfDayEnum
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


def _require_intervall_mode(session: Session, person_id: uuid.UUID) -> None:
    """Guard: blockiert Aktionen, die im Simple-Modus nicht zulässig sind.

    Im Simple-Modus werden Person-TODs automatisch aus Project-Defaults
    abgeleitet; manuelles Bearbeiten bleibt deaktiviert.
    """
    if service.is_simple_mode_for_person(session, person_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Im Simple-Modus werden Tageszeiten vom Projekt verwaltet",
        )


# ── Hauptseite ────────────────────────────────────────────────────────────────


@router.get("", response_class=HTMLResponse)
def availability_page(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    plan_period_id: uuid.UUID | None = Query(default=None),
    team_id: uuid.UUID | None = Query(default=None),
    at: str | None = Query(default=None),
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
        session,
        person_id,
        active,
        teams=teams,
        selected_team_id=selected_team_id,
        open_periods=open_periods,
        position=at,
    )

    nav = view_model.period_nav
    period_nav_json = {
        "prev":  str(nav.prev_plan_period_id)  if nav.prev_plan_period_id  else None,
        "next":  str(nav.next_plan_period_id)  if nav.next_plan_period_id  else None,
        "today": str(nav.today_plan_period_id) if nav.today_plan_period_id else None,
        "todayInActive": nav.today_in_active,
    }
    selected_team_id_json = str(selected_team_id) if selected_team_id else None

    return templates.TemplateResponse(
        "availability/index.html",
        {
            "request": request,
            "user": user,
            "view_model": view_model,
            "open_periods": open_periods,
            "initial_position": at or "",
            "period_nav_json": period_nav_json,
            "selected_team_id_json": selected_team_id_json,
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
    """Serverseitig gerendertes Wochen-Grid (TimeGrid-Layout) für HTMX-Einbindung."""
    person_id = _require_person(user)
    app = service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    period_start = app.plan_period.start
    period_end = app.plan_period.end
    week_end = start + timedelta(days=6)
    markers = service.get_markers_for_range(session, actor_plan_period_id, start, week_end)

    # Sichtfenster + TimeGrid-Layout berechnen
    view_start_min, view_end_min = service.compute_view_window(markers)
    slots_by_day = service.layout_week_grid(markers, view_start_min, view_end_min)

    # Tage-Liste (Mo–So) inkl. Slots pro Tag — Slots können leer sein
    days_list: list[tuple[date, list[service.WeekGridSlot]]] = []
    for i in range(7):
        d = start + timedelta(days=i)
        days_list.append((d, slots_by_day.get(d, [])))

    # Stundenmarken für die Time-Axis (volle Stunden im Sichtfenster)
    hour_marks = list(range(view_start_min // 60, view_end_min // 60 + 1))

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
            "view_start_min": view_start_min,
            "view_end_min": view_end_min,
            "hour_marks": hour_marks,
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
    is_locked = pp.closed
    is_simple = service.is_simple_mode_for_person(session, person_id)
    if is_simple:
        detail = service.get_day_detail_simple(
            session, actor_plan_period_id, person_id, day, is_locked,
        )
    else:
        detail = service.get_day_detail(
            session, actor_plan_period_id, person_id, day, is_locked,
        )
    return templates.TemplateResponse(
        "availability/partials/day_panel.html",
        {"request": request, "detail": detail, "is_simple_mode": is_simple},
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
    service.check_closed_or_403(app.plan_period)

    if service.find_avail_day(session, actor_plan_period_id, day, time_of_day_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Verfügbarkeitstag existiert bereits")

    service.create_avail_day(session, actor_plan_period_id, day, time_of_day_id)

    enum_id = service.enum_id_for_tod(session, time_of_day_id)
    return _render_enum_group(
        request, session, app, person_id, day, enum_id, is_simple=False,
    )


@router.delete("/avail-day/by-enum", response_class=HTMLResponse)
def delete_avail_day_by_enum(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    actor_plan_period_id: uuid.UUID = Query(...),
    day: date = Query(...),
    time_of_day_enum_id: uuid.UUID = Query(...),
):
    """Simple-Mode-Delete: löscht ALLE AvailDays für (app, day, enum).

    Inklusive etwaiger Altlasten aus dem Intervall-Modus, die auf andere TODs
    desselben Enums zeigten. `has_appointment` wird pro AvailDay vorgeprüft —
    wenn irgendeiner eingeplant ist, 409 ohne Löschung.

    MUSS vor `/avail-day/{avail_day_id}` registriert sein: FastAPI matcht
    Routen in Registrierungsreihenfolge — sonst wird "by-enum" als UUID-Param
    interpretiert und Pydantic wirft 422 beim UUID-Parse.
    """
    person_id = _require_person(user)
    if not service.is_simple_mode_for_person(session, person_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Simple-Mode ist für dieses Projekt nicht aktiv",
        )
    app = service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    service.check_closed_or_403(app.plan_period)

    # Alle betroffenen AvailDays auf Appointments prüfen
    existing = service.find_avail_day_by_enum(session, actor_plan_period_id, day, time_of_day_enum_id)
    if existing is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Verfügbarkeitstag nicht gefunden")

    # Iterativ: alle AvailDays dieses Enums für diesen Tag laden und jeden prüfen
    ad_ids = session.execute(
        sa_select(AvailDay.id)
        .join(TimeOfDay, TimeOfDay.id == AvailDay.time_of_day_id)
        .where(AvailDay.actor_plan_period_id == actor_plan_period_id)
        .where(AvailDay.date == day)
        .where(AvailDay.prep_delete.is_(None))
        .where(TimeOfDay.time_of_day_enum_id == time_of_day_enum_id)
    ).scalars().all()
    for ad_id in ad_ids:
        if service.has_appointment(session, ad_id):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="Verfügbarkeitstag ist bereits eingeplant",
            )

    service.delete_avail_days_by_enum(session, actor_plan_period_id, day, time_of_day_enum_id)

    return _render_enum_group(
        request, session, app, person_id, day, time_of_day_enum_id, is_simple=True,
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
    service.check_closed_or_403(app.plan_period)

    if service.has_appointment(session, avail_day_id):
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Verfügbarkeitstag ist bereits eingeplant")

    day = ad.date
    actor_plan_period_id = ad.actor_plan_period_id
    # Enum-ID VOR dem Delete ermitteln — danach ist der AvailDay soft-deleted
    # und der Join-Helper liefert nichts mehr.
    enum_id = service.enum_id_for_avail_day(session, avail_day_id)
    service.delete_avail_day(session, avail_day_id)

    is_simple = service.is_simple_mode_for_person(session, person_id)
    return _render_enum_group(
        request, session, app, person_id, day, enum_id, is_simple=is_simple,
    )


# ── AvailDay Mutations: Simple-Mode-Variante ─────────────────────────────────


@router.post("/avail-day/simple", response_class=HTMLResponse)
def create_avail_day_simple(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    actor_plan_period_id: uuid.UUID = Form(...),
    day: date = Form(...),
    time_of_day_enum_id: uuid.UUID = Form(...),
):
    """Simple-Mode-Create: User klickt nur das Enum, Server bestimmt primary TOD."""
    person_id = _require_person(user)
    if not service.is_simple_mode_for_person(session, person_id):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Simple-Mode ist für dieses Projekt nicht aktiv",
        )
    app = service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    service.check_closed_or_403(app.plan_period)

    # Enum gehört zum Projekt der Person?
    person = session.get(Person, person_id)
    enum = session.get(TimeOfDayEnum, time_of_day_enum_id)
    if enum is None or enum.project_id != person.project_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Tageszeit-Kategorie nicht gefunden")

    # Uniqueness per Enum (nicht per TOD-Id): existiert bereits ein AvailDay?
    if service.find_avail_day_by_enum(session, actor_plan_period_id, day, time_of_day_enum_id) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="Verfügbarkeitstag existiert bereits")

    primary = service.ensure_simple_primary_tod(session, person, enum)
    if primary is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Keine Tageszeit für dieses Enum definiert — bitte Disponenten kontaktieren",
        )

    service.create_avail_day(session, actor_plan_period_id, day, primary.id)

    return _render_enum_group(
        request, session, app, person_id, day, time_of_day_enum_id, is_simple=True,
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
    service.check_closed_or_403(app.plan_period)

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
    _require_intervall_mode(session, person_id)
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
    _require_intervall_mode(session, person_id)
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
    _require_intervall_mode(session, person_id)
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
    _require_intervall_mode(session, person_id)
    tod = service.authorize_person_time_of_day(session, person_id, tod_id)
    if service.count_avail_days_for_tod(session, tod_id) > 0:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="Tageszeit wird noch von Verfügbarkeitstagen genutzt",
        )
    service.remove_person_time_of_day(session, person_id, tod)
    return HTMLResponse("")  # hx-swap=outerHTML → Zeile verschwindet


# ── Sidebar-Stats Refresh (HTMX-Trigger nach Mutation) ───────────────────────


@router.get("/sidebar-stats", response_class=HTMLResponse)
def sidebar_stats(
    request: Request,
    user: LoggedInUser,
    session: Session = Depends(get_db_session),
    actor_plan_period_id: uuid.UUID = Query(...),
):
    """Liefert nur das Sidebar-Stats-Fragment — wird via HX-Trigger
    `availability-changed` aus den Mutation-Endpoints angestoßen."""
    person_id = _require_person(user)
    app = service.authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    stats = service.get_sidebar_stats(session, actor_plan_period_id, app.requested_assignments)
    return templates.TemplateResponse(
        "availability/partials/sidebar_period_stats.html",
        {"request": request, "stats": stats},
    )


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────


def _render_enum_group(
    request: Request,
    session: Session,
    app: service.ActorPlanPeriod,
    person_id: uuid.UUID,
    day: date,
    enum_id: uuid.UUID | None,
    is_simple: bool,
):
    """Rendert eine einzelne Enum-Gruppe als HTMX-Partial nach einer Mutation.

    Setzt `HX-Trigger: availability-changed` damit Sidebar-Stats und Kalender
    sich auf Client-Seite refreshen können. Per-Group-Swap statt Full-Day-Panel
    macht parallele Klicks unabhängig (kein Race auf #day-panel).

    `enum_id` darf None sein (nur theoretisch, wenn die Helper-Funktion
    ausnahmsweise nichts findet) — dann gibt's einen leeren Body, dem User
    fehlt visuell nichts, weil der ursprüngliche Server-Stand bestehen bleibt.
    """
    detail = service.DayDetailViewModel(
        day=day,
        actor_plan_period_id=app.id,
        is_locked=service.is_app_locked(app),
        enum_groups=[],
    )
    grp = None
    if enum_id is not None:
        if is_simple:
            grp = service.get_enum_group_detail_simple(session, app.id, person_id, day, enum_id)
        else:
            grp = service.get_enum_group_detail(session, app.id, person_id, day, enum_id)

    headers = {"HX-Trigger": "availability-changed"}
    if grp is None:
        return HTMLResponse("", headers=headers)
    return templates.TemplateResponse(
        "availability/partials/_enum_group.html",
        {"request": request, "grp": grp, "detail": detail, "is_simple_mode": is_simple},
        headers=headers,
    )
