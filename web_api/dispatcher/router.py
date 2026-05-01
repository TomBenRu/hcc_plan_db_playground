"""Router: Dispatcher-Endpoints."""

import logging
import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from sqlalchemy import select as sa_select
from sqlalchemy.orm import selectinload

from database.models import (
    Address,
    Appointment,
    LocationOfWork,
    LocationPlanPeriod,
    Plan,
    PlanPeriod,
    Team,
    TeamLocationAssign,
    TimeOfDay,
)
from web_api.auth.dependencies import WebUserRole, require_role
from web_api.cancellations.service import get_cancellations_for_dispatcher
from web_api.common import fc_event_end_iso, fc_event_start_iso, guest_list, location_display_name
from web_api.user_settings.service import get_color_overrides
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
    set_cast_group_nr_actors,
)
from web_api.email.service import schedule_emails
from web_api.employees.service import get_coworkers_for_appointment
from web_api.models.web_models import WebUser
from web_api.plan_adjustment.service import (
    create_appointment_with_event,
    delete_appointment,
    preview_appointment_delete,
)
from web_api.templating import templates

logger = logging.getLogger(__name__)

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


# ── Appointment-CRUD (D3) ────────────────────────────────────────────────────
# Diese Endpoints MÜSSEN vor `/plan/appointments/{appointment_id}` registriert
# sein, sonst frisst die catch-all Path-Param-Route den `new`-Pfad und wirft 422
# beim UUID-Parse (siehe Memory `feedback_htmx_form_query_params`).


# Warning-Zustände für das Last-Minute-Modal — siehe _resolve_appointment_form_state.
_WARNING_OK = "ok"
_WARNING_NO_PLAN_PERIOD = "no_plan_period"
_WARNING_NO_BINDING_PLAN = "no_binding_plan"
_WARNING_NO_LPP = "no_lpp"


def _load_locations_for_team(
    session: Session,
    team_id: uuid.UUID,
    *,
    date_filter: date | None = None,
) -> list[dict]:
    """Locations, die dem Team am gewählten Tag zugeordnet sind.

    Quelle: `TeamLocationAssign` mit tagesgenauer Range
    `start <= date < end` (end IS NULL → unbefristete Zuordnung).
    """
    location_query = (
        sa_select(LocationOfWork.id, LocationOfWork.name, Address.city)
        .select_from(LocationOfWork)
        .join(Address, Address.id == LocationOfWork.address_id, isouter=True)
        .join(TeamLocationAssign, TeamLocationAssign.location_of_work_id == LocationOfWork.id)
        .where(TeamLocationAssign.team_id == team_id)
        .where(LocationOfWork.prep_delete.is_(None))
    )
    if date_filter is not None:
        location_query = (
            location_query
            .where(TeamLocationAssign.start <= date_filter)
            .where(
                (TeamLocationAssign.end.is_(None))
                | (TeamLocationAssign.end > date_filter)
            )
        )
    location_query = location_query.distinct().order_by(LocationOfWork.name)

    location_rows = list(session.execute(location_query).mappings().all())
    return [
        {"id": row["id"], "display_name": location_display_name(row["name"], row["city"])}
        for row in location_rows
    ]


def _resolve_appointment_form_state(
    session: Session,
    *,
    team_id: uuid.UUID,
    date_filter: date | None,
    location_id: uuid.UUID | None,
) -> dict:
    """Auflösung (Team, Datum, Location) → Form-Zustand für das Last-Minute-Modal.

    Liefert ein Dict mit:
    - `time_of_days`: list[dict] mit id/name/start/is_standard, sortiert nach start
    - `default_time_of_day_id`: UUID | None (zeitlich erste aus time_of_day_standards)
    - `nr_actors`: int (Prefill-Wert für Cast-Soll-Größe)
    - `warning_state`: str (siehe _WARNING_*-Konstanten)
    - `submit_enabled`: bool (False, wenn kein bindender Plan ODER keine PlanPeriode)

    Logik:
    1. Datum oder Location nicht gesetzt → leer + warning=ok (initial-state, kein Banner)
    2. Keine PlanPeriode für (team, date) → leer + warning=no_plan_period, submit=False
    3. Kein bindender Plan in der Periode → TODs/nr_actors aus LPP laden falls vorhanden,
       warning=no_binding_plan, submit=False (Last-Minute nur auf bindendem Plan erlaubt)
    4. Bindender Plan + LPP fehlt (Location nicht in Periode) → leer + warning=no_lpp,
       submit=False
    5. Alles ok → TODs/nr_actors aus LPP, warning=ok, submit=True
    """
    empty_state = {
        "time_of_days": [],
        "default_time_of_day_id": None,
        "nr_actors": 1,
        "warning_state": _WARNING_OK,
        "submit_enabled": False,
    }

    if date_filter is None:
        return empty_state

    plan_period = session.execute(
        sa_select(PlanPeriod)
        .join(Team, Team.id == PlanPeriod.team_id)
        .where(PlanPeriod.team_id == team_id)
        .where(PlanPeriod.start <= date_filter)
        .where(PlanPeriod.end >= date_filter)
        .where(PlanPeriod.prep_delete.is_(None))
        .where(Team.prep_delete.is_(None))
    ).scalars().first()

    if plan_period is None:
        return {**empty_state, "warning_state": _WARNING_NO_PLAN_PERIOD}

    has_binding_plan = session.execute(
        sa_select(Plan.id)
        .where(Plan.plan_period_id == plan_period.id)
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
    ).scalars().first() is not None

    if not has_binding_plan:
        # Banner sofort zeigen — auch ohne Location-Auswahl, sonst sieht der User
        # erst nach Location-Wechsel, dass die ganze Periode noch keinen bindenden
        # Plan hat. Submit bleibt in jedem Fall blockiert.
        if location_id is None:
            return {**empty_state, "warning_state": _WARNING_NO_BINDING_PLAN}
        lpp = session.execute(
            sa_select(LocationPlanPeriod)
            .options(
                selectinload(LocationPlanPeriod.time_of_days),
                selectinload(LocationPlanPeriod.time_of_day_standards),
            )
            .where(LocationPlanPeriod.plan_period_id == plan_period.id)
            .where(LocationPlanPeriod.location_of_work_id == location_id)
        ).scalars().first()
        if lpp is None:
            return {**empty_state, "warning_state": _WARNING_NO_BINDING_PLAN}
        return {
            **_build_lpp_form_data(lpp),
            "warning_state": _WARNING_NO_BINDING_PLAN,
            "submit_enabled": False,
        }

    if location_id is None:
        # PlanPeriode + bindender Plan ok, aber Location noch nicht ausgewählt.
        # Form ist neutral, Submit-Button bleibt aus, bis Location gesetzt ist.
        return empty_state

    lpp = session.execute(
        sa_select(LocationPlanPeriod)
        .options(
            selectinload(LocationPlanPeriod.time_of_days),
            selectinload(LocationPlanPeriod.time_of_day_standards),
        )
        .where(LocationPlanPeriod.plan_period_id == plan_period.id)
        .where(LocationPlanPeriod.location_of_work_id == location_id)
    ).scalars().first()

    if lpp is None:
        return {**empty_state, "warning_state": _WARNING_NO_LPP}

    lpp_data = _build_lpp_form_data(lpp)
    return {
        **lpp_data,
        "warning_state": _WARNING_OK,
        # Edge-Case: LPP existiert, aber alle TODs sind soft-deleted.
        # Dropdown zeigt seinen Empty-State, Submit-Button bleibt aus.
        "submit_enabled": bool(lpp_data["time_of_days"]),
    }


def _build_lpp_form_data(lpp: LocationPlanPeriod) -> dict:
    """TODs + nr_actors aus einer geladenen LPP extrahieren.

    TODs werden nach `start` sortiert; jede TOD bekommt ein `is_standard`-Flag.
    Default-TOD ist die zeitlich erste aus `time_of_day_standards`.
    """
    standard_ids = {tod.id for tod in lpp.time_of_day_standards if tod.prep_delete is None}
    active_tods = sorted(
        (t for t in lpp.time_of_days if t.prep_delete is None),
        key=lambda t: t.start,
    )
    time_of_days = [
        {
            "id": t.id,
            "name": t.name,
            "start": t.start,
            "is_standard": t.id in standard_ids,
        }
        for t in active_tods
    ]
    standard_active_sorted = [t for t in active_tods if t.id in standard_ids]
    default_id = standard_active_sorted[0].id if standard_active_sorted else None

    return {
        "time_of_days": time_of_days,
        "default_time_of_day_id": default_id,
        "nr_actors": lpp.nr_actors if lpp.nr_actors is not None else 1,
    }


def _parse_optional_date(date_str: str | None) -> date | None:
    if not date_str:
        return None
    try:
        return date.fromisoformat(date_str)
    except ValueError:
        return None


def _parse_optional_uuid(value: str | None) -> uuid.UUID | None:
    """`hx-include` sendet leere Selects als leeren String — als None behandeln."""
    if not value:
        return None
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


def _build_form_context(
    session: Session,
    *,
    request: Request,
    my_teams: list,
    selected_team,
    parsed_date: date | None,
    location_id: uuid.UUID | None,
    error_message: str | None,
) -> dict:
    """Komplettes Template-Context für das Initial-Render des Last-Minute-Modals.

    Lädt Locations + State (TODs/nr_actors/warning/submit-enabled) und gleicht
    die übergebene location_id auf eine real verfügbare ab (Fallback: erste der
    aktuellen Locations-Liste).
    """
    locations = _load_locations_for_team(
        session, selected_team.id, date_filter=parsed_date
    )
    effective_location_id = location_id
    if locations and not any(loc["id"] == effective_location_id for loc in locations):
        effective_location_id = locations[0]["id"]
    elif not locations:
        effective_location_id = None

    state = _resolve_appointment_form_state(
        session,
        team_id=selected_team.id,
        date_filter=parsed_date,
        location_id=effective_location_id,
    )

    return {
        "request": request,
        "my_teams": my_teams,
        "selected_team_id": selected_team.id,
        "default_date": parsed_date.isoformat() if parsed_date else "",
        "locations": locations,
        "selected_location_id": effective_location_id,
        "error_message": error_message,
        **state,
    }


@router.get("/plan/appointments/new", response_class=HTMLResponse)
def dispatcher_appointment_new_form(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = Query(default=None),
    date_str: str | None = Query(default=None, alias="date"),
    location_of_work_id_str: str | None = Query(default=None, alias="location_of_work_id"),
):
    """HTMX-Modal-Fragment: Form zum Anlegen eines Termins.

    `team_id`, `date` und `location_of_work_id` sind optional. Beim Team-Wechsel
    lädt das Form sich neu (Full-Render); bei Datums- oder Location-Wechsel
    nutzt der Client den Refresh-Endpoint mit OOB-Swaps, um nur betroffene Felder
    auszutauschen ohne Verlust eingegebener Notizen.
    """
    person_id = _require_person_id(user)
    my_teams = get_teams_for_dispatcher(session, person_id)
    if not my_teams:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Sie haben kein Team zur Disposition.",
        )

    selected_team = None
    if team_id is not None:
        selected_team = next((t for t in my_teams if t.id == team_id), None)
    if selected_team is None:
        selected_team = my_teams[0]

    parsed_date = _parse_optional_date(date_str)
    parsed_location_id = _parse_optional_uuid(location_of_work_id_str)

    context = _build_form_context(
        session,
        request=request,
        my_teams=my_teams,
        selected_team=selected_team,
        parsed_date=parsed_date,
        location_id=parsed_location_id,
        error_message=None,
    )
    return templates.TemplateResponse(
        "dispatcher/partials/appointment_create_form.html",
        context,
    )


@router.get("/plan/appointments/new/refresh", response_class=HTMLResponse)
def dispatcher_appointment_new_refresh(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID = Query(...),
    date_str: str | None = Query(default=None, alias="date"),
    location_of_work_id_str: str | None = Query(default=None, alias="location_of_work_id"),
    trigger: str = Query(default="location"),
):
    """OOB-Refresh-Endpoint für das Last-Minute-Modal.

    Wird bei Datums- oder Location-Wechsel im offenen Form aufgerufen und liefert
    eine Response mit ausschliesslich `hx-swap-oob`-Snippets — der Form-State
    (z.B. eingegebene Notizen) bleibt dadurch erhalten.

    `trigger` steuert, ob die Locations-Liste mitgerendert wird:
        - "team" oder "date" → Locations + TODs + nr_actors + Warning + Submit
        - "location"        → TODs + nr_actors + Warning + Submit (Locations bleiben)
    """
    person_id = _require_person_id(user)
    my_teams = get_teams_for_dispatcher(session, person_id)
    selected_team = next((t for t in my_teams if t.id == team_id), None)
    if selected_team is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Sie sind nicht Dispatcher dieses Teams.",
        )

    parsed_date = _parse_optional_date(date_str)
    parsed_location_id = _parse_optional_uuid(location_of_work_id_str)
    include_locations = trigger in ("team", "date")

    locations: list[dict] = []
    effective_location_id = parsed_location_id
    if include_locations:
        locations = _load_locations_for_team(
            session, selected_team.id, date_filter=parsed_date
        )
        if locations and not any(loc["id"] == effective_location_id for loc in locations):
            effective_location_id = locations[0]["id"]
        elif not locations:
            effective_location_id = None

    state = _resolve_appointment_form_state(
        session,
        team_id=selected_team.id,
        date_filter=parsed_date,
        location_id=effective_location_id,
    )

    return templates.TemplateResponse(
        "dispatcher/partials/_appt_form_oob_snippets.html",
        {
            "request": request,
            "include_locations": include_locations,
            "locations": locations,
            "selected_location_id": effective_location_id,
            **state,
        },
    )


@router.post("/plan/appointments", response_class=HTMLResponse)
def dispatcher_appointment_create(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID = Form(...),
    date: date = Form(...),
    location_of_work_id: uuid.UUID = Form(...),
    time_of_day_id: uuid.UUID = Form(...),
    nr_actors: int = Form(...),
    notes: str = Form(default=""),
):
    """Atomarer Create-Submit. Bei Erfolg: 204 + HX-Trigger.
    Bei Validierungsfehler: Form re-rendern mit Banner."""
    person_id = _require_person_id(user)
    my_teams = get_teams_for_dispatcher(session, person_id)
    selected_team = next((t for t in my_teams if t.id == team_id), None)
    if selected_team is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Sie sind nicht Dispatcher dieses Teams.",
        )

    # Server-Validierung: muss matchen, was das Form clientseitig erlaubt.
    # Schützt vor manipulierten Submissions (z.B. fremde TimeOfDay-IDs aus dem
    # Project-Default-Pool, die in der LPP gar nicht zugelassen sind).
    state = _resolve_appointment_form_state(
        session,
        team_id=team_id,
        date_filter=date,
        location_id=location_of_work_id,
    )
    error_message: str | None = None
    if state["warning_state"] == _WARNING_NO_PLAN_PERIOD:
        error_message = "Für dieses Datum existiert keine Plan-Periode für das Team."
    elif state["warning_state"] == _WARNING_NO_BINDING_PLAN:
        error_message = (
            "Last-Minute-Buchungen sind nicht möglich, "
            "solange kein bindender Plan veröffentlicht ist."
        )
    elif state["warning_state"] == _WARNING_NO_LPP:
        error_message = "Diese Location ist in der Plan-Periode nicht vorgesehen."
    elif not any(t["id"] == time_of_day_id for t in state["time_of_days"]):
        error_message = "Diese Tageszeit ist für die gewählte Location-Plan-Periode nicht zulässig."

    if error_message is None:
        try:
            create_appointment_with_event(
                session,
                team_id=team_id,
                date=date,
                location_of_work_id=location_of_work_id,
                time_of_day_id=time_of_day_id,
                nr_actors=nr_actors,
                notes=notes.strip() or None,
            )
        except HTTPException as exc:
            if exc.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
                raise  # Server-Fehler durchreichen
            error_message = exc.detail
        except Exception as exc:
            error_message = f"Termin konnte nicht angelegt werden: {exc}"

    if error_message is not None:
        session.rollback()
        context = _build_form_context(
            session,
            request=request,
            my_teams=my_teams,
            selected_team=selected_team,
            parsed_date=date,
            location_id=location_of_work_id,
            error_message=error_message,
        )
        return templates.TemplateResponse(
            "dispatcher/partials/appointment_create_form.html",
            context,
            status_code=status.HTTP_200_OK,
        )

    session.commit()
    # Leeres 200-HTML statt 204: HTMX verarbeitet HX-Trigger bei 204 nicht
    # zuverlaessig. Empty-Body wird in #modal-root geswappt → Modal-Inhalt
    # leer, plus hcc:close-modal-Trigger schliesst das Modal.
    # Empty-HTML 200 + HX-Trigger-After-Settle: 204 No Content erzeugt KEINEN
    # Swap-Cycle, daher feuert HX-Trigger-After-Settle dort unzuverlaessig
    # (settle-Phase findet ohne Swap nicht statt). Mit Empty-200 wird ein
    # echter Swap durchgefuehrt (Modal-Inhalt geleert), Settle laeuft, und
    # beide Listener (hcc:close-modal + hcc:appointments-changed) feuern sicher.
    response = HTMLResponse(content="", status_code=status.HTTP_200_OK)
    response.headers["HX-Trigger-After-Settle"] = "hcc:close-modal, hcc:appointments-changed"
    return response


@router.get("/plan/appointments/{appointment_id}/delete-modal", response_class=HTMLResponse)
def dispatcher_appointment_delete_modal(
    request: Request,
    force_event_delete: bool = Query(default=False),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
):
    """HTMX-Modal-Fragment: Lösch-Bestätigung mit N×M×force-Konstellations-Text.

    Force-Checkbox triggert `hx-get` auf denselben Endpoint mit aktualisiertem
    `force_event_delete`-Param → Modal-Body rendert die passende Variante.
    """
    preview = preview_appointment_delete(session, appointment.id)
    return templates.TemplateResponse(
        "dispatcher/partials/appointment_delete_modal.html",
        {
            "request": request,
            "appointment_id": appointment.id,
            "preview": preview,
            "force": force_event_delete,
        },
    )


@router.delete("/plan/appointments/{appointment_id}", response_class=HTMLResponse)
def dispatcher_appointment_delete(
    background_tasks: BackgroundTasks,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    force_event_delete: bool = Form(default=False),
    send_notifications: bool = Form(default=True),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
):
    """Hard-Delete des Appointments + bedingte Event-Löschung.

    - N=0: Event mit löschen (Default-Verhalten ohne User-Choice)
    - N>0, force=False: nur Appointment, Event bleibt
    - N>0, force=True: Event mit löschen, kaskadiert N andere Appointments

    Notifications: Verplante des aktuellen Appointments + pending Request-
    Inhaber im aktuellen Plan. Verplante in nicht-binding Iterationen werden
    NICHT informiert (PRD F3.3).

    Pro-Aktion-Toggle `send_notifications` (Default ON): bei OFF wird kein
    Inbox/Email gesendet — stattdessen schreibt der Service einen
    structured `logger.info("audit.notification_suppressed", ...)`-Eintrag
    als Stop-Gap zur künftigen Audit-Tabelle. DB-Mutation findet trotzdem
    statt.
    """
    payloads = delete_appointment(
        session,
        appointment.id,
        actor_user_id=user.id,
        force_event_delete=force_event_delete,
        send_notifications=send_notifications,
    )
    session.commit()
    schedule_emails(background_tasks, payloads, session)

    # Leeres 200-HTML statt 204 (siehe Begründung oben am Create-Endpoint)
    # Empty-HTML 200 + HX-Trigger-After-Settle: 204 No Content erzeugt KEINEN
    # Swap-Cycle, daher feuert HX-Trigger-After-Settle dort unzuverlaessig
    # (settle-Phase findet ohne Swap nicht statt). Mit Empty-200 wird ein
    # echter Swap durchgefuehrt (Modal-Inhalt geleert), Settle laeuft, und
    # beide Listener (hcc:close-modal + hcc:appointments-changed) feuern sicher.
    response = HTMLResponse(content="", status_code=status.HTTP_200_OK)
    response.headers["HX-Trigger-After-Settle"] = "hcc:close-modal, hcc:appointments-changed"
    return response


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

    overrides = get_color_overrides(session, user.id)
    event = get_appointment_detail_for_dispatcher(session, appointment_id, allowed_ids, user_overrides=overrides)
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
            "guests": guest_list(appointment.guests) if appointment else [],
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
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
):
    """HTMX-Fragment: Cast-Display (Status + Mitarbeiter-Liste).

    Der Edit-Flow läuft über das separate Modal-Fragment (`/cast/edit-modal`).
    """
    status_data = get_cast_status_for_appointment(session, appointment.id)
    coworkers = get_coworkers_for_appointment(session, appointment.id)
    return templates.TemplateResponse(
        "dispatcher/partials/cast_display.html",
        {
            "request": request,
            "appointment": appointment,
            "coworkers": coworkers,
            "guests": guest_list(appointment.guests),
            "cast_count": status_data["cast_count"],
            "cast_required": status_data["cast_required"],
            "is_understaffed": status_data["is_understaffed"],
        },
    )


@router.get("/plan/appointments/{appointment_id}/cast/edit-modal", response_class=HTMLResponse)
def dispatcher_cast_edit_modal(
    request: Request,
    show_all: bool = Query(default=False),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
):
    """HTMX-Fragment: Cast-Edit-Modal.

    Wird in `#modal-root` geswapt. Enthält Soll-Größe (nr_actors) als Input,
    Mitarbeiter-Auswahl, Gäste-Verwaltung und Live-Zähler.

    `show_all=True` blendet auch nicht-verfügbare Team-Mitarbeiter ein (als
    ausgegraute Einträge mit Tooltip).
    """
    candidates = get_team_availability_for_appointment(session, appointment.id)
    status_data = get_cast_status_for_appointment(session, appointment.id)
    return templates.TemplateResponse(
        "dispatcher/partials/cast_edit_modal.html",
        {
            "request": request,
            "appointment": appointment,
            "candidates": candidates,
            "guests": guest_list(appointment.guests),
            "nr_actors": status_data["cast_required"],
            "show_all": show_all,
        },
    )


@router.patch("/plan/appointments/{appointment_id}/cast/nr-actors")
def dispatcher_update_nr_actors(
    nr_actors: int = Form(...),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
):
    """Setzt die Soll-Besetzung der CastGroup des Events.

    Wirkt auf **alle** Appointments desselben Events (CastGroup ist
    event-global). Liefert 204 No Content — die Warnung über
    Über-/Unterbesetzung wird client-seitig aus dem Live-Zähler
    abgeleitet, weil der Server-State nicht den noch ungespeicherten
    Cast-Zustand des offenen Modals kennt.
    """
    set_cast_group_nr_actors(session, appointment.id, nr_actors)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"HX-Trigger": "hcc:cast-changed"})


@router.patch("/plan/appointments/{appointment_id}/avail-days", response_class=HTMLResponse)
def dispatcher_update_cast(
    request: Request,
    background_tasks: BackgroundTasks,
    person_ids: list[uuid.UUID] = Form(default_factory=list),
    guests: list[str] = Form(default_factory=list),
    appointment: Appointment = Depends(require_team_dispatcher_for_appointment),
    session: Session = Depends(get_db_session),
):
    """Speichert Cast-Änderung (Personen + Gäste); liefert Display-Fragment.

    Response-Header `HX-Trigger`:
      - `hcc:cast-changed` — triggert Kalender-Refresh (Unterbesetzungs-Dot).
      - `hcc:close-modal` — signalisiert dem Client, das offene Modal zu schließen.

    Audit: Wenn der Dispatcher (typischerweise via `show_all=1`) eine Person
    speichert, die für diesen Slot als blockiert markiert ist (Zeit-Konflikt
    oder unzulässige Location-Kombination), wird das mit `logger.warning`
    festgehalten. `no_avail_day` zählt nicht als Override — dort wird der
    AvailDay automatisch angelegt.
    """
    candidates_by_id = {
        c.person_id: c
        for c in get_team_availability_for_appointment(session, appointment.id)
    }
    overrides = [
        candidates_by_id[pid]
        for pid in person_ids
        if pid in candidates_by_id
        and candidates_by_id[pid].blocked_reason in ("time_overlap", "location_combo")
    ]
    if overrides:
        logger.warning(
            "Cast-Override: dispatcher persisted %d blocked candidate(s) for appointment %s: %s",
            len(overrides),
            appointment.id,
            [
                {
                    "person_id": str(c.person_id),
                    "reason": c.blocked_reason,
                    "info": c.blocking_info,
                }
                for c in overrides
            ],
        )

    payloads = replace_cast_for_appointment(
        session, appointment.id, person_ids, guests=guests
    )
    session.commit()
    schedule_emails(background_tasks, payloads, session)

    status_data = get_cast_status_for_appointment(session, appointment.id)
    coworkers = get_coworkers_for_appointment(session, appointment.id)
    response = templates.TemplateResponse(
        "dispatcher/partials/cast_display.html",
        {
            "request": request,
            "appointment": appointment,
            "coworkers": coworkers,
            "guests": guest_list(appointment.guests),
            "cast_count": status_data["cast_count"],
            "cast_required": status_data["cast_required"],
            "is_understaffed": status_data["is_understaffed"],
        },
    )
    response.headers["HX-Trigger"] = "hcc:cast-changed, hcc:close-modal"
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