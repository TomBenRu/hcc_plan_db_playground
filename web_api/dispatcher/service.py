"""Service-Schicht für die Dispatcher-Plan-Ansicht.

Spiegelt `web_api/employees/service.py`, filtert jedoch auf Team-Ebene
(PlanPeriod.team_id) statt auf Person-Ebene (ActorPlanPeriod.person_id).
"""

import uuid
from dataclasses import dataclass
from datetime import date, time

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
    Project,
    Team,
    TimeOfDay,
    TimeOfDayEnum,
)
from web_api.availability.service import create_avail_day, find_avail_day
from web_api.common import guest_count
from web_api.email.service import EmailPayload
from web_api.employees.service import CalendarEvent, location_color
from web_api.plan_adjustment.service import update_appointment_avail_days


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
        guests_count = guest_count(r["guests"])
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


def _interval_minutes(start: time, end: time) -> tuple[int, int]:
    """Normalisiert ein TimeOfDay-Intervall auf Minuten seit Tages-Start.

    Slots können über Mitternacht reichen (z. B. 22:00–02:00). Wenn
    `end < start`, wird `end += 24h` addiert — so ist der Vergleich
    monoton und das übliche `a_start <= b_start AND a_end >= b_end`-
    Containment funktioniert korrekt für alle Fälle.
    """
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    if end_min < start_min:
        end_min += 24 * 60
    return start_min, end_min


def get_team_availability_for_appointment(
    session: Session,
    appointment_id: uuid.UUID,
) -> list[CastCandidate]:
    """Alle Team-Mitarbeiter der Plan-Periode mit Verfügbarkeits- und
    Zuordnungs-Meta für den Event-Slot dieses Appointments.

    Eine Person gilt als `is_available`, wenn sie am Event-Datum einen
    `AvailDay` hat, dessen Zeit-Intervall das Event-Intervall einschließt
    (`avail.start ≤ event.start` und `avail.end ≥ event.end`). TimeOfDay-
    IDs werden **nicht** direkt verglichen — im Datenmodell werden
    TimeOfDay-Instanzen auf jeder Hierarchie-Ebene neu angelegt
    (Project → Person → ActorPlanPeriod → AvailDay), mit potenziell
    abweichenden start/end-Werten. Der Intervall-Vergleich ist der
    semantisch korrekte Match. Mitternachts-Spannen werden via
    `_interval_minutes` normalisiert (end += 24h bei end < start).

    `is_currently_assigned` bleibt unabhängig über die Link-Chain zur
    ActorPlanPeriod ermittelt — auch Solver-Zuordnungen mit vom Slot
    abweichendem time_of_day werden korrekt als zugeordnet gemeldet.
    """
    ctx_row = session.execute(
        sa_select(
            Event.date.label("event_date"),
            TimeOfDay.start.label("event_start"),
            TimeOfDay.end.label("event_end"),
            TimeOfDayEnum.time_index.label("event_time_index"),
            Plan.plan_period_id.label("plan_period_id"),
            Project.use_simple_time_slots.label("use_simple"),
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(TimeOfDayEnum, TimeOfDayEnum.id == TimeOfDay.time_of_day_enum_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .join(Team, Team.id == PlanPeriod.team_id)
        .join(Project, Project.id == Team.project_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()
    if ctx_row is None:
        return []

    event_date = ctx_row["event_date"]
    plan_period_id = ctx_row["plan_period_id"]
    use_simple = bool(ctx_row["use_simple"])
    event_time_index = int(ctx_row["event_time_index"])
    event_start_min, event_end_min = _interval_minutes(
        ctx_row["event_start"], ctx_row["event_end"]
    )

    # ActorPlanPeriod-IDs, die aktuell an diesem Appointment zugeordnet sind.
    current_app_ids = set(session.execute(
        sa_select(AvailDay.actor_plan_period_id)
        .join(AvailDayAppointmentLink,
              AvailDayAppointmentLink.avail_day_id == AvailDay.id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
    ).scalars().all())

    # Alle Personen der Plan-Periode
    person_rows = session.execute(
        sa_select(
            Person.id.label("person_id"),
            Person.f_name,
            Person.l_name,
            ActorPlanPeriod.id.label("actor_plan_period_id"),
        )
        .select_from(ActorPlanPeriod)
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .where(ActorPlanPeriod.plan_period_id == plan_period_id)
        .order_by(Person.l_name, Person.f_name)
    ).mappings().all()

    # Alle AvailDays am Event-Datum für diese Plan-Periode.
    # `avail_time_index` wird für den Simple-Modus verwendet, `avail_start`/
    # `avail_end` für den Intervall-Modus — in einer Query geladen, im
    # Matching-Loop verzweigt.
    avail_rows = session.execute(
        sa_select(
            AvailDay.id.label("avail_day_id"),
            AvailDay.actor_plan_period_id.label("actor_plan_period_id"),
            TimeOfDay.start.label("avail_start"),
            TimeOfDay.end.label("avail_end"),
            TimeOfDayEnum.time_index.label("avail_time_index"),
        )
        .select_from(AvailDay)
        .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .join(TimeOfDay, TimeOfDay.id == AvailDay.time_of_day_id)
        .join(TimeOfDayEnum, TimeOfDayEnum.id == TimeOfDay.time_of_day_enum_id)
        .where(ActorPlanPeriod.plan_period_id == plan_period_id)
        .where(AvailDay.date == event_date)
        .where(AvailDay.prep_delete.is_(None))
    ).mappings().all()

    # Gruppiere AvailDays nach ActorPlanPeriod; pro Person den ersten AvailDay
    # finden, der das Match-Kriterium erfüllt. Kriterium ist modus-abhängig:
    # - Simple-Modus: gleicher `time_index`.
    # - Intervall-Modus (Default): `avail.start ≤ event.start AND avail.end ≥ event.end`
    #   (mit Mitternachts-Normalisierung via _interval_minutes).
    avails_by_app: dict[uuid.UUID, list[dict]] = {}
    for a in avail_rows:
        avails_by_app.setdefault(a["actor_plan_period_id"], []).append(dict(a))

    def _is_match(a: dict) -> bool:
        if use_simple:
            return int(a["avail_time_index"]) == event_time_index
        a_start_min, a_end_min = _interval_minutes(a["avail_start"], a["avail_end"])
        return a_start_min <= event_start_min and a_end_min >= event_end_min

    result: list[CastCandidate] = []
    for p in person_rows:
        app_id = p["actor_plan_period_id"]
        matching_avail_id: uuid.UUID | None = None
        for a in avails_by_app.get(app_id, []):
            if _is_match(a):
                matching_avail_id = a["avail_day_id"]
                break
        result.append(CastCandidate(
            person_id=p["person_id"],
            full_name=f"{p['f_name']} {p['l_name']}",
            initials=_compute_initials(p["f_name"], p["l_name"]),
            actor_plan_period_id=app_id,
            is_currently_assigned=app_id in current_app_ids,
            is_available=matching_avail_id is not None,
            avail_day_id=matching_avail_id,
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

    guests_count = guest_count(ctx_row["guests"])
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