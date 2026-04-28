"""Router: Dispatcher-Endpoints."""

import uuid
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlmodel import Session

from sqlalchemy import select as sa_select

from database.models import Address, Appointment, LocationOfWork, TimeOfDay
from web_api.auth.dependencies import WebUserRole, require_role
from web_api.cancellations.service import get_cancellations_for_dispatcher
from web_api.common import fc_event_end_iso, fc_event_start_iso, guest_list, location_display_name
from web_api.config import get_settings
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
from web_api.email.service import send_emails_background
from web_api.employees.service import get_coworkers_for_appointment
from web_api.models.web_models import WebUser
from web_api.plan_adjustment.service import create_appointment_with_event
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


def _load_appointment_form_options(session: Session, team) -> dict:
    """Lädt Locations + Project-Default-TODs für ein Team-Project.

    Locations: alle aktiven LocationOfWork des Projects.
    TODs: alle TimeOfDay mit `project_defaults_id == team.project_id`
    (= Project-Defaults, die im UI als Standard-Auswahl dienen).
    """
    location_rows = list(session.execute(
        sa_select(LocationOfWork.id, LocationOfWork.name, Address.city)
        .select_from(LocationOfWork)
        .join(Address, Address.id == LocationOfWork.address_id, isouter=True)
        .where(LocationOfWork.project_id == team.project_id)
        .where(LocationOfWork.prep_delete.is_(None))
        .order_by(LocationOfWork.name)
    ).mappings().all())
    locations = [
        {"id": row["id"], "display_name": location_display_name(row["name"], row["city"])}
        for row in location_rows
    ]

    tod_rows = list(session.execute(
        sa_select(TimeOfDay.id, TimeOfDay.name, TimeOfDay.start)
        .where(TimeOfDay.project_defaults_id == team.project_id)
        .where(TimeOfDay.prep_delete.is_(None))
        .order_by(TimeOfDay.start)
    ).mappings().all())
    time_of_days = [dict(row) for row in tod_rows]

    return {"locations": locations, "time_of_days": time_of_days}


@router.get("/plan/appointments/new", response_class=HTMLResponse)
def dispatcher_appointment_new_form(
    request: Request,
    user: WebUser = require_role(WebUserRole.dispatcher, WebUserRole.admin),
    session: Session = Depends(get_db_session),
    team_id: uuid.UUID | None = Query(default=None),
    date: str | None = Query(default=None),
):
    """HTMX-Modal-Fragment: Form zum Anlegen eines Termins.

    `team_id` und `date` sind optional — `date` wird per Day-Click prefilled,
    `team_id` per Team-Select-Wechsel. Bei Team-Wechsel (hx-trigger=change)
    lädt das Form sich selbst neu mit aktualisierten Location- und TOD-Listen.
    """
    person_id = _require_person_id(user)
    my_teams = get_teams_for_dispatcher(session, person_id)
    if not my_teams:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Sie haben kein Team zur Disposition.",
        )

    # Team auswählen: gewähltes Team falls erlaubt, sonst erstes my_team
    selected_team = None
    if team_id is not None:
        selected_team = next((t for t in my_teams if t.id == team_id), None)
    if selected_team is None:
        selected_team = my_teams[0]

    options = _load_appointment_form_options(session, selected_team)

    return templates.TemplateResponse(
        "dispatcher/partials/appointment_create_form.html",
        {
            "request": request,
            "my_teams": my_teams,
            "selected_team_id": selected_team.id,
            "default_date": date or "",
            "locations": options["locations"],
            "time_of_days": options["time_of_days"],
            "error_message": None,
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

    error_message: str | None = None
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
        options = _load_appointment_form_options(session, selected_team)
        return templates.TemplateResponse(
            "dispatcher/partials/appointment_create_form.html",
            {
                "request": request,
                "my_teams": my_teams,
                "selected_team_id": selected_team.id,
                "default_date": date.isoformat(),
                "locations": options["locations"],
                "time_of_days": options["time_of_days"],
                "error_message": error_message,
            },
            status_code=status.HTTP_200_OK,
        )

    session.commit()
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.headers["HX-Trigger"] = "hcc:close-modal, hcc:appointments-changed"
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
    settings=Depends(get_settings),
):
    """Speichert Cast-Änderung (Personen + Gäste); liefert Display-Fragment.

    Response-Header `HX-Trigger`:
      - `hcc:cast-changed` — triggert Kalender-Refresh (Unterbesetzungs-Dot).
      - `hcc:close-modal` — signalisiert dem Client, das offene Modal zu schließen.
    """
    payloads = replace_cast_for_appointment(
        session, appointment.id, person_ids, guests=guests
    )
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