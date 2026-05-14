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
    get_person_detail,
    get_user_project_id,
    list_persons_in_project,
    resolve_selected_team,
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
    at: str | None = Query(default=None),
):
    """Projektweite Plan-Sicht — alle Teams, Read-only.

    Optionales `at=YYYY-MM-DD` steuert das Initial-Datum des FullCalendars —
    erlaubt Deep-Links wie /viewer/plan?teams=…&at=2026-09-01 aus der
    Planperioden-Liste, damit der Read-Nutzer direkt im richtigen Zeitfenster
    landet statt auf 'heute' (was bei zukuenftigen Perioden eine leere Sicht
    erzeugt).
    """
    project_id = get_user_project_id(session, user)
    my_teams = get_all_teams_in_project(session, project_id)
    allowed_ids = [t.id for t in my_teams]
    effective_ids = filter_allowed_team_ids(teams, allowed_ids)

    initial_date = date.today().isoformat()
    if at:
        try:
            initial_date = date.fromisoformat(at).isoformat()
        except ValueError:
            pass  # Ungueltiger Param → Fallback auf heute

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


# ── Planperioden-Uebersicht (Read-Only) ──────────────────────────────────────


@router.get("/periods", response_class=HTMLResponse)
def viewer_periods(
    request: Request,
    user: WebUser = require_role(WebUserRole.viewer, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = None,
    status_filter: str | None = None,
):
    """Projektweite Planperioden-Liste, Read-Only.

    Wir nutzen `db_services.PlanPeriod.get_all_from__team_minimal` (gleicher
    Datenpfad wie der Dispatcher-View) und reichen `filter_periods` durch
    die Status-Auswahl. Im Gegensatz zum Dispatcher gibt's hier:
      - alle Teams des Projekts in der Sidebar (statt Dispatcher-Teams)
      - keine Edit-/Close-/Delete-Aktionen
      - statt "Neue Periode" einen "Plan ansehen"-Link zum /viewer/plan
    """
    from database import db_services
    from web_api.dispatcher_periods.service import filter_periods

    project_id = get_user_project_id(session, user)
    teams = get_all_teams_in_project(session, project_id)
    selected_team_id = resolve_selected_team(
        session,
        project_id=project_id,
        requested_team_id=team_id,
        available_teams=teams,
    )

    if selected_team_id:
        periods = db_services.PlanPeriod.get_all_from__team_minimal(
            selected_team_id, include_deleted=True,
        )
    else:
        periods = []
    periods = filter_periods(periods, status_filter)
    periods = sorted(periods, key=lambda p: p.start, reverse=True)

    return templates.TemplateResponse(
        "viewer/periods/index.html",
        {
            "request": request,
            "user": user,
            "teams": teams,
            "selected_team_id": selected_team_id,
            "status_filter": status_filter,
            "periods": periods,
        },
    )


# ── Personen-Stammdaten (Read-Only) ──────────────────────────────────────────


@router.get("/persons", response_class=HTMLResponse)
def viewer_persons(
    request: Request,
    user: WebUser = require_role(WebUserRole.viewer, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = None,
    include_deleted: bool = Query(default=False),
    search: str = Query(default=""),
):
    """Read-Only-Listenseite der Mitarbeiter im Projekt mit Filtern."""
    project_id = get_user_project_id(session, user)
    teams = get_all_teams_in_project(session, project_id)
    rows = list_persons_in_project(
        session,
        project_id=project_id,
        team_id=team_id,
        include_deleted=include_deleted,
        search=search,
    )
    return templates.TemplateResponse(
        "viewer/persons/index.html",
        {
            "request": request,
            "user": user,
            "teams": teams,
            "selected_team_id": team_id,
            "rows": rows,
            "filters": {
                "team_id": team_id,
                "include_deleted": include_deleted,
                "search": search,
            },
        },
    )


@router.get("/persons/{person_id}/drawer", response_class=HTMLResponse)
def viewer_person_drawer(
    person_id: uuid.UUID,
    request: Request,
    user: WebUser = require_role(WebUserRole.viewer, WebUserRole.admin),
    session: Session = Depends(get_db_session),
):
    """Detail-Drawer einer Person — read-only, Cross-Project-404."""
    project_id = get_user_project_id(session, user)
    detail = get_person_detail(session, project_id=project_id, person_id=person_id)
    return templates.TemplateResponse(
        "viewer/persons/partials/drawer.html",
        {
            "request": request,
            "detail": detail,
            "today_date": date.today(),
        },
    )


# ── Verfuegbarkeiten Pro-Person (Read-Only) ──────────────────────────────────


@router.get("/availability", response_class=HTMLResponse)
def viewer_availability(
    request: Request,
    user: WebUser = require_role(WebUserRole.viewer, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    person_id: uuid.UUID | None = Query(default=None),
    actor_plan_period_id: uuid.UUID | None = Query(default=None),
    search: str = Query(default=""),
):
    """Pro-Person-Sicht der Verfuegbarkeiten.

    Layout: Sidebar mit Personen-Auswahl + Suche, Hauptbereich zeigt die
    AvailDays der gewaehlten Person fuer die gewaehlte Plan-Periode als
    FullCalendar. Mutationen gibt es bewusst nicht — read-only spiegelt
    die `/availability/`-Sicht des Mitarbeiters wider.
    """
    from web_api.availability.service import (
        get_open_plan_periods_for_person,
    )

    project_id = get_user_project_id(session, user)
    # Personenliste: Filter via search, ohne Team-Filter — der Viewer sucht
    # gezielt nach einer Person.
    persons = list_persons_in_project(
        session,
        project_id=project_id,
        team_id=None,
        include_deleted=False,
        search=search,
    )

    selected_person = None
    open_periods: list = []
    active_period = None

    if person_id is not None:
        # Project-Scope-Check: Person muss zum Projekt des Viewers gehoeren.
        try:
            detail = get_person_detail(
                session, project_id=project_id, person_id=person_id
            )
            selected_person = detail.person
        except Exception:
            selected_person = None  # 404 stillschweigend ausblenden

        if selected_person is not None:
            open_periods = get_open_plan_periods_for_person(session, person_id)
            if open_periods:
                active_period = next(
                    (p for p in open_periods if p.actor_plan_period_id == actor_plan_period_id),
                    open_periods[0],
                )

    return templates.TemplateResponse(
        "viewer/availability/index.html",
        {
            "request": request,
            "user": user,
            "persons": persons,
            "selected_person_id": person_id,
            "selected_person": selected_person,
            "open_periods": open_periods,
            "active_period": active_period,
            "search": search,
        },
    )


@router.get("/availability/events")
def viewer_availability_events(
    user: WebUser = require_role(WebUserRole.viewer, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    person_id: uuid.UUID = Query(...),
    actor_plan_period_id: uuid.UUID = Query(...),
    start: date = Query(...),
    end: date = Query(...),
):
    """FullCalendar-JSON: AvailDays einer Person im sichtbaren Datumsbereich.

    Project-Scope-Check stellt sicher, dass der Viewer die Person nicht aus
    einem fremden Projekt querfragen kann. Authorize_actor_plan_period
    prueft zusaetzlich, dass die APP zur Person gehoert.
    """
    from web_api.availability.service import (
        authorize_actor_plan_period,
        get_markers_for_range,
    )

    project_id = get_user_project_id(session, user)
    # Person muss zum Projekt gehoeren (sonst Cross-Project-Leak).
    get_person_detail(session, project_id=project_id, person_id=person_id)

    authorize_actor_plan_period(session, person_id, actor_plan_period_id)
    markers = get_markers_for_range(session, actor_plan_period_id, start, end)

    # Farbpalette identisch zum /availability/events-Endpoint — gleiches
    # Look-and-Feel fuer den Viewer.
    palette = ["#F97316", "#38BDF8", "#2DD4BF", "#818CF8", "#F472B6", "#4ADE80"]
    return [
        {
            "id": str(m.avail_day_id),
            "title": m.time_of_day_enum_abbreviation,
            "start": m.day.isoformat(),
            "allDay": True,
            "color": palette[m.time_of_day_enum_time_index % len(palette)],
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