"""Service-Schicht für die Dispatcher-Plan-Ansicht.

Spiegelt `web_api/employees/service.py`, filtert jedoch auf Team-Ebene
(PlanPeriod.team_id) statt auf Person-Ebene (ActorPlanPeriod.person_id).
"""

import json
import uuid
from dataclasses import dataclass
from datetime import date
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    CastGroup,
    Event,
    LocationOfWork,
    LocationPlanPeriod,
    Person,
    Plan,
    PlanPeriod,
    Team,
    TimeOfDay,
)
from web_api.availability.service import create_avail_day, find_avail_day
from web_api.email.service import EmailPayload
from web_api.employees.service import CalendarEvent, location_color
from web_api.plan_adjustment.service import update_appointment_avail_days


def _guest_count(value: Any) -> int:
    """Zählt Gäste robust — auch wenn SQLAlchemy den JSON-Wert als String
    durchreicht statt ihn zu dekodieren. Fallback: 0 bei leerem/ungültigem
    Wert statt Zeichen-Zählen.
    """
    if isinstance(value, (list, tuple)):
        return len(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            if isinstance(parsed, (list, tuple)):
                return len(parsed)
        except (ValueError, TypeError):
            pass
    return 0


@dataclass
class TeamInfo:
    id: uuid.UUID
    name: str


def get_teams_for_dispatcher(
    session: Session,
    person_id: uuid.UUID,
) -> list[TeamInfo]:
    """Alle Teams, für die die Person als Dispatcher eingetragen ist."""
    rows = session.execute(
        sa_select(Team.id, Team.name)
        .where(Team.dispatcher_id == person_id)
        .order_by(Team.name)
    ).mappings().all()
    return [TeamInfo(id=r["id"], name=r["name"]) for r in rows]


def get_appointments_for_teams(
    session: Session,
    team_ids: list[uuid.UUID],
    start_date: date | None = None,
    end_date: date | None = None,
    only_understaffed: bool = False,
) -> list[CalendarEvent]:
    """Alle Appointments der angegebenen Teams als CalendarEvents.

    Mit `only_understaffed=True` wird das Ergebnis nach dem CalendarEvent-
    Build gefiltert (Python-Filter, nicht SQL-HAVING — die is_understaffed-
    Berechnung kombiniert avail-count und JSON-Guests-Länge und lässt sich
    nicht trivial in SQL ausdrücken).
    """
    if not team_ids:
        return []

    # Subquery: AvailDay-Count pro Appointment (= „besetzt durch Mitarbeiter")
    avail_count_subq = (
        sa_select(
            AvailDayAppointmentLink.appointment_id.label("appointment_id"),
            func.count(AvailDayAppointmentLink.avail_day_id).label("avail_count"),
        )
        .group_by(AvailDayAppointmentLink.appointment_id)
        .subquery()
    )

    stmt = (
        sa_select(
            Appointment.id.label("appointment_id"),
            Appointment.notes.label("appointment_notes"),
            Appointment.guests.label("guests"),
            Event.date.label("event_date"),
            LocationOfWork.name.label("location_name"),
            LocationOfWork.id.label("location_id"),
            TimeOfDay.name.label("time_of_day_name"),
            TimeOfDay.start.label("time_start"),
            TimeOfDay.end.label("time_end"),
            PlanPeriod.id.label("plan_period_id"),
            PlanPeriod.start.label("period_start"),
            PlanPeriod.end.label("period_end"),
            PlanPeriod.team_id.label("team_id"),
            CastGroup.nr_actors.label("cast_required"),
            func.coalesce(avail_count_subq.c.avail_count, 0).label("avail_count"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod,
              LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork,
              LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .join(CastGroup, CastGroup.id == Event.cast_group_id)
        .outerjoin(avail_count_subq,
                   avail_count_subq.c.appointment_id == Appointment.id)
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
        .where(PlanPeriod.team_id.in_(team_ids))
        .where(Appointment.prep_delete.is_(None))
        .where(Event.prep_delete.is_(None))
        .order_by(Event.date, TimeOfDay.start)
    )

    if start_date:
        stmt = stmt.where(Event.date >= start_date)
    if end_date:
        stmt = stmt.where(Event.date <= end_date)

    rows = session.execute(stmt).mappings().all()

    result: list[CalendarEvent] = []
    for r in rows:
        guests_count = _guest_count(r["guests"])
        cast_count = int(r["avail_count"]) + guests_count
        cast_required = int(r["cast_required"])
        result.append(CalendarEvent(
            appointment_id=r["appointment_id"],
            event_date=r["event_date"],
            location_name=r["location_name"],
            location_id=r["location_id"],
            color=location_color(r["location_id"]),
            time_of_day_name=r["time_of_day_name"],
            time_start=r["time_start"],
            time_end=r["time_end"],
            appointment_notes=r["appointment_notes"],
            plan_period_id=r["plan_period_id"],
            period_start=r["period_start"],
            period_end=r["period_end"],
            team_id=r["team_id"],
            cast_count=cast_count,
            cast_required=cast_required,
            is_understaffed=cast_count < cast_required,
        ))

    if only_understaffed:
        result = [ev for ev in result if ev.is_understaffed]
    return result


def get_appointment_detail_for_dispatcher(
    session: Session,
    appointment_id: uuid.UUID,
    allowed_team_ids: list[uuid.UUID],
) -> CalendarEvent | None:
    """Einzelner Appointment — nur wenn er zu einem erlaubten Team gehört."""
    events = get_appointments_for_teams(session, allowed_team_ids)
    for ev in events:
        if ev.appointment_id == appointment_id:
            return ev
    return None


def filter_allowed_team_ids(
    requested: list[uuid.UUID],
    allowed: list[uuid.UUID],
) -> list[uuid.UUID]:
    """Schnittmenge: gibt nur Team-IDs zurück, für die der User Dispatcher ist.

    Verhindert, dass ein Dispatcher per Query-Param die Pläne fremder Teams
    sieht. Leerer `requested` bedeutet „alle erlaubten Teams".
    """
    allowed_set = set(allowed)
    if not requested:
        return list(allowed)
    return [tid for tid in requested if tid in allowed_set]


# ── Cast-Change (D2) ──────────────────────────────────────────────────────────


@dataclass
class CastCandidate:
    person_id: uuid.UUID
    full_name: str
    initials: str
    actor_plan_period_id: uuid.UUID
    is_currently_assigned: bool
    is_available: bool
    avail_day_id: uuid.UUID | None


def _compute_initials(f_name: str | None, l_name: str | None) -> str:
    if f_name and l_name:
        return f"{f_name[0]}{l_name[0]}".upper()
    if f_name:
        return f_name[0].upper()
    if l_name:
        return l_name[0].upper()
    return "?"


def get_team_availability_for_appointment(
    session: Session,
    appointment_id: uuid.UUID,
) -> list[CastCandidate]:
    """Alle Team-Mitarbeiter der Plan-Periode mit Verfügbarkeits- und
    Zuordnungs-Meta für den Event-Slot dieses Appointments.

    Liefert pro Person, ob sie für den Slot einen `AvailDay` hat
    (`is_available`) und ob sie dem Appointment bereits zugeordnet ist
    (`is_currently_assigned`). Im Default-Rendering zeigt das UI nur
    diejenigen mit mindestens einem der beiden Flags; der „Alle"-Toggle
    schaltet auf die vollständige Liste um.
    """
    ctx_row = session.execute(
        sa_select(
            Event.date.label("event_date"),
            Event.time_of_day_id.label("time_of_day_id"),
            Plan.plan_period_id.label("plan_period_id"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()
    if ctx_row is None:
        return []

    event_date = ctx_row["event_date"]
    time_of_day_id = ctx_row["time_of_day_id"]
    plan_period_id = ctx_row["plan_period_id"]

    # ActorPlanPeriod-IDs, die aktuell an diesem Appointment zugeordnet sind.
    # Wir joinen über den AvailDayAppointmentLink, unabhängig davon, ob der
    # zugeordnete AvailDay mit dem Slot (date/time_of_day) exakt übereinstimmt —
    # Solver-generierte Zuordnungen können abweichende AvailDays nutzen.
    current_app_ids = set(session.execute(
        sa_select(AvailDay.actor_plan_period_id)
        .join(AvailDayAppointmentLink,
              AvailDayAppointmentLink.avail_day_id == AvailDay.id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalars().all())

    stmt = (
        sa_select(
            Person.id.label("person_id"),
            Person.f_name,
            Person.l_name,
            ActorPlanPeriod.id.label("actor_plan_period_id"),
            AvailDay.id.label("avail_day_id"),
        )
        .select_from(ActorPlanPeriod)
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .outerjoin(
            AvailDay,
            (AvailDay.actor_plan_period_id == ActorPlanPeriod.id)
            & (AvailDay.date == event_date)
            & (AvailDay.time_of_day_id == time_of_day_id)
            & (AvailDay.prep_delete.is_(None))
        )
        .where(ActorPlanPeriod.plan_period_id == plan_period_id)
        .order_by(Person.l_name, Person.f_name)
    )
    rows = session.execute(stmt).mappings().all()

    result: list[CastCandidate] = []
    for r in rows:
        avail_day_id = r["avail_day_id"]
        result.append(CastCandidate(
            person_id=r["person_id"],
            full_name=f"{r['f_name']} {r['l_name']}",
            initials=_compute_initials(r["f_name"], r["l_name"]),
            actor_plan_period_id=r["actor_plan_period_id"],
            is_currently_assigned=r["actor_plan_period_id"] in current_app_ids,
            is_available=avail_day_id is not None,
            avail_day_id=avail_day_id,
        ))
    return result


def get_cast_status_for_appointment(
    session: Session,
    appointment_id: uuid.UUID,
) -> dict:
    """Lädt Besetzungs-Zähler für einen einzelnen Appointment.

    Nutzt dieselbe Definition wie `get_appointments_for_teams`:
    `cast_count = len(avail_days) + len(guests)`. Liefert dict mit
    `cast_count`, `cast_required`, `is_understaffed`.
    """
    avail_count = session.execute(
        sa_select(func.count(AvailDayAppointmentLink.avail_day_id))
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalar_one()

    ctx_row = session.execute(
        sa_select(
            Appointment.guests.label("guests"),
            CastGroup.nr_actors.label("cast_required"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(CastGroup, CastGroup.id == Event.cast_group_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()
    if ctx_row is None:
        return {"cast_count": 0, "cast_required": 0, "is_understaffed": False}

    guests_count = _guest_count(ctx_row["guests"])
    cast_count = int(avail_count) + guests_count
    cast_required = int(ctx_row["cast_required"])
    return {
        "cast_count": cast_count,
        "cast_required": cast_required,
        "is_understaffed": cast_count < cast_required,
    }


def replace_cast_for_appointment(
    session: Session,
    appointment_id: uuid.UUID,
    person_ids: list[uuid.UUID],
) -> list[EmailPayload]:
    """Ersetzt die Cast-Zuordnung eines Appointments anhand von Person-IDs.

    Für jede person_id wird der passende `ActorPlanPeriod` in der Plan-
    Periode gesucht und ein `AvailDay` für den Event-Slot gefunden oder
    angelegt (via `create_avail_day` — erlaubt Zuordnung von aktuell
    nicht-verfügbaren Personen). Ruft dann `update_appointment_avail_days`
    aus `plan_adjustment/service.py`, welches die M:N-Zuordnung ersetzt
    und offene Requests entfernter Personen auf `superseded_by_cast_change`
    flippt + Notification-Payloads erzeugt.
    """
    ctx_row = session.execute(
        sa_select(
            Event.date.label("event_date"),
            Event.time_of_day_id.label("time_of_day_id"),
            Plan.plan_period_id.label("plan_period_id"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()
    if ctx_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Termin nicht gefunden")

    event_date = ctx_row["event_date"]
    time_of_day_id = ctx_row["time_of_day_id"]
    plan_period_id = ctx_row["plan_period_id"]

    avail_day_ids: list[uuid.UUID] = []
    if person_ids:
        app_rows = session.execute(
            sa_select(ActorPlanPeriod.id, ActorPlanPeriod.person_id)
            .where(ActorPlanPeriod.plan_period_id == plan_period_id)
            .where(ActorPlanPeriod.person_id.in_(person_ids))
        ).mappings().all()
        apps_by_person = {r["person_id"]: r["id"] for r in app_rows}

        missing = set(person_ids) - set(apps_by_person.keys())
        if missing:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Person nicht in der Plan-Periode planbar",
            )

        for pid in person_ids:
            app_id = apps_by_person[pid]
            avail_day = find_avail_day(session, app_id, event_date, time_of_day_id)
            if avail_day is None:
                avail_day = create_avail_day(session, app_id, event_date, time_of_day_id)
            avail_day_ids.append(avail_day.id)

    return update_appointment_avail_days(session, appointment_id, avail_day_ids)