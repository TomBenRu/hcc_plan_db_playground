"""Service-Schicht für den Mitarbeiter-Kalender.

Join-Kette:
  Appointment → AvailDayAppointmentLink → AvailDay → ActorPlanPeriod → Person
             → Event → TimeOfDay
             → Event → LocationPlanPeriod → LocationOfWork
             → Plan  → PlanPeriod
"""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select as sa_select
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
from web_api.common import guest_count
from web_api.models.web_models import (
    CancellationRequest,
    CancellationStatus,
    SwapRequest,
    SwapRequestStatus,
)
from web_api.settings.service import get_effective_deadline

# ── Farb-Palette für Einsatzorte ──────────────────────────────────────────────
_LOCATION_COLORS = [
    "#F97316",  # orange  (Brand)
    "#38BDF8",  # sky
    "#2DD4BF",  # teal
    "#818CF8",  # indigo
    "#F472B6",  # pink
    "#4ADE80",  # grün
    "#FB923C",  # orange-400
    "#A78BFA",  # violet
]


def location_color(location_id: uuid.UUID) -> str:
    """Deterministisch: gleicher Ort → gleiche Farbe."""
    return _LOCATION_COLORS[hash(str(location_id)) % len(_LOCATION_COLORS)]


# ── Datenklassen ──────────────────────────────────────────────────────────────


@dataclass
class CalendarEvent:
    appointment_id: uuid.UUID
    event_date: date
    location_name: str
    location_id: uuid.UUID
    color: str
    time_of_day_name: str | None
    time_start: time | None
    time_end: time | None
    appointment_notes: str | None
    plan_period_id: uuid.UUID
    period_start: date
    period_end: date
    team_id: uuid.UUID | None = None
    is_binding: bool = True
    has_pending_cancellation: bool = False
    has_active_swap_request: bool = False
    is_past_deadline: bool = False
    # Besetzungs-Metadaten (Defaults: neutral, damit Employee-Pfad unverändert bleibt)
    cast_count: int = 0
    cast_required: int = 0
    is_understaffed: bool = False
    # True = Person ist bei diesem Termin eingeteilt; False = fremder Termin (E1-Show-All)
    is_own: bool = True


@dataclass
class PlanPeriodInfo:
    id: uuid.UUID
    start: date
    end: date

    @property
    def label(self) -> str:
        months_de = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun",
                     "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
        s = f"{self.start.day}. {months_de[self.start.month - 1]} {self.start.year}"
        e = f"{self.end.day}. {months_de[self.end.month - 1]} {self.end.year}"
        return f"{s} – {e}"


# ── Queries ───────────────────────────────────────────────────────────────────


def get_plan_periods_for_person(
    session: Session,
    person_id: uuid.UUID,
) -> list[PlanPeriodInfo]:
    """Alle PlanPeriods, in denen die Person einen ActorPlanPeriod hat (neueste zuerst)."""
    rows = session.execute(
        sa_select(PlanPeriod)
        .join(ActorPlanPeriod, ActorPlanPeriod.plan_period_id == PlanPeriod.id)
        .where(ActorPlanPeriod.person_id == person_id)
        .where(PlanPeriod.prep_delete.is_(None))
        .order_by(PlanPeriod.start.desc())
        .distinct()
    ).scalars().all()

    seen: set[tuple[date, date]] = set()
    result: list[PlanPeriodInfo] = []
    for pp in rows:
        key = (pp.start, pp.end)
        if key not in seen:
            seen.add(key)
            result.append(PlanPeriodInfo(id=pp.id, start=pp.start, end=pp.end))
    return result


def get_appointments_for_person(
    session: Session,
    person_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[CalendarEvent]:
    """Join-Query über alle Ebenen. Liefert CalendarEvents für FullCalendar."""
    stmt = (
        sa_select(
            Appointment.id.label("appointment_id"),
            Appointment.notes.label("appointment_notes"),
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
        )
        .select_from(Appointment)
        .join(AvailDayAppointmentLink,
              AvailDayAppointmentLink.appointment_id == Appointment.id)
        .join(AvailDay,
              AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .join(ActorPlanPeriod,
              ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .join(Event, Event.id == Appointment.event_id)
        .join(LocationPlanPeriod,
              LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork,
              LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
        .where(ActorPlanPeriod.person_id == person_id)
        .where(Appointment.prep_delete.is_(None))
        .where(Event.prep_delete.is_(None))
        .order_by(Event.date, TimeOfDay.start)
    )

    if start_date:
        stmt = stmt.where(Event.date >= start_date)
    if end_date:
        stmt = stmt.where(Event.date <= end_date)

    rows = session.execute(stmt).mappings().all()

    # Batch-Query: welche Appointments haben eine offene Absage?
    appointment_ids = [row["appointment_id"] for row in rows]
    pending_cancellation_ids: set[uuid.UUID] = set()
    active_swap_request_ids: set[uuid.UUID] = set()
    if appointment_ids:
        pending_cancellation_ids = set(
            session.execute(
                sa_select(CancellationRequest.appointment_id)
                .where(CancellationRequest.appointment_id.in_(appointment_ids))
                .where(CancellationRequest.status == CancellationStatus.pending)
            ).scalars().all()
        )
        # Batch-Query: welche Appointments sind bereits als Anfragender in einer aktiven Tauschanfrage?
        active_swap_request_ids = set(
            session.execute(
                sa_select(SwapRequest.requester_appointment_id)
                .where(SwapRequest.requester_appointment_id.in_(appointment_ids))
                .where(SwapRequest.status.in_([
                    SwapRequestStatus.pending,
                    SwapRequestStatus.accepted_by_target,
                ]))
            ).scalars().all()
        )

    # Batch-Load: Deadlines je Team (eine DB-Abfrage je unique team_id)
    unique_team_ids = {row["team_id"] for row in rows if row["team_id"] is not None}
    deadline_hours_by_team: dict[uuid.UUID, int] = {
        tid: get_effective_deadline(session, tid).deadline_hours
        for tid in unique_team_ids
    }

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    def _is_past_deadline(team_id: uuid.UUID | None, event_date: date, time_start: time | None) -> bool:
        if team_id is None or time_start is None:
            return False
        dl = deadline_hours_by_team.get(team_id, 0)
        if dl <= 0:
            return False
        cutoff = datetime.combine(event_date, time_start) - timedelta(hours=dl)
        return now > cutoff

    return [
        CalendarEvent(
            appointment_id=row["appointment_id"],
            event_date=row["event_date"],
            location_name=row["location_name"],
            location_id=row["location_id"],
            color=location_color(row["location_id"]),
            time_of_day_name=row["time_of_day_name"],
            time_start=row["time_start"],
            time_end=row["time_end"],
            appointment_notes=row["appointment_notes"],
            plan_period_id=row["plan_period_id"],
            period_start=row["period_start"],
            period_end=row["period_end"],
            team_id=row["team_id"],
            has_pending_cancellation=row["appointment_id"] in pending_cancellation_ids,
            has_active_swap_request=row["appointment_id"] in active_swap_request_ids,
            is_past_deadline=_is_past_deadline(
                row["team_id"], row["event_date"], row["time_start"]
            ),
        )
        for row in rows
    ]


def get_appointment_detail(
    session: Session,
    appointment_id: uuid.UUID,
    person_id: uuid.UUID,
) -> CalendarEvent | None:
    """Einzelner Appointment — nur wenn er der Person gehört."""
    results = get_appointments_for_person(
        session, person_id,
    )
    for ev in results:
        if ev.appointment_id == appointment_id:
            return ev
    return None


def get_team_ids_for_person(session: Session, person_id: uuid.UUID) -> list[uuid.UUID]:
    """Alle Teams, in denen die Person ActorPlanPeriods hat (aktiv oder historisch)."""
    return list(session.execute(
        sa_select(PlanPeriod.team_id)
        .join(ActorPlanPeriod, ActorPlanPeriod.plan_period_id == PlanPeriod.id)
        .where(ActorPlanPeriod.person_id == person_id)
        .where(PlanPeriod.prep_delete.is_(None))
        .distinct()
    ).scalars().all())


def get_team_appointments_for_person(
    session: Session,
    person_id: uuid.UUID,
    start_date: date | None = None,
    end_date: date | None = None,
    only_understaffed: bool = False,
) -> list[CalendarEvent]:
    """Alle Termine in den Teams der Person (auch fremde Zuordnungen).

    Analog zum Dispatcher-Pattern (`get_appointments_for_teams`): Besetzungs-Count
    kommt aus einer Subquery über AvailDay-Einsätze plus `Appointment.guests`.
    Enrichment-Felder (`has_pending_cancellation`, `has_active_swap_request`,
    `is_past_deadline`) bleiben Default `False` — sie sind nur für eigene Termine
    semantisch sinnvoll und werden vom Caller für die Person-Teilmenge ergänzt.
    """
    team_ids = get_team_ids_for_person(session, person_id)
    if not team_ids:
        return []

    # Subquery: Anzahl zugeordneter AvailDays je Appointment
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
        .join(LocationPlanPeriod, LocationPlanPeriod.id == Event.location_plan_period_id)
        .join(LocationOfWork, LocationOfWork.id == LocationPlanPeriod.location_of_work_id)
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .join(PlanPeriod, PlanPeriod.id == Plan.plan_period_id)
        .join(CastGroup, CastGroup.id == Event.cast_group_id)
        .join(avail_count_subq, avail_count_subq.c.appointment_id == Appointment.id, isouter=True)
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
        guests = guest_count(r["guests"])
        cc = int(r["avail_count"]) + guests
        cr = int(r["cast_required"])
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
            cast_count=cc,
            cast_required=cr,
            is_understaffed=cc < cr,
        ))

    if only_understaffed:
        result = [ev for ev in result if ev.is_understaffed]
    return result


def get_appointment_detail_for_team(
    session: Session,
    appointment_id: uuid.UUID,
    person_id: uuid.UUID,
) -> CalendarEvent | None:
    """Team-autorisiertes Detail-Lookup für fremde Termine (E1-Show-All).

    Erlaubt den Detail-Abruf, wenn der Appointment in einem Team liegt, in dem die
    Person ActorPlanPeriods hat — auch wenn sie selbst nicht eingeteilt ist.
    Rückgabe enthält `is_own=False` und neutrale Enrichment-Felder.
    """
    team_ids = get_team_ids_for_person(session, person_id)
    if not team_ids:
        return None
    # Range bewusst weit — wir filtern auf appointment_id in-memory, um die Team-
    # Query nicht zu duplizieren.
    candidates = get_team_appointments_for_person(session, person_id)
    for ev in candidates:
        if ev.appointment_id == appointment_id:
            ev.is_own = False
            return ev
    return None


@dataclass
class CoWorker:
    person_id: uuid.UUID
    f_name: str
    l_name: str

    @property
    def full_name(self) -> str:
        return f"{self.f_name} {self.l_name}"

    @property
    def initials(self) -> str:
        return f"{self.f_name[0]}{self.l_name[0]}".upper() if self.f_name and self.l_name else "?"


def get_coworkers_for_appointment(
    session: Session,
    appointment_id: uuid.UUID,
) -> list[CoWorker]:
    """Alle Personen, die am gleichen Event (event_id) eingesetzt sind."""
    event_id_subq = (
        sa_select(Appointment.event_id)
        .where(Appointment.id == appointment_id)
        .scalar_subquery()
    )

    stmt = (
        sa_select(Person.id, Person.f_name, Person.l_name)
        .select_from(Appointment)
        .join(AvailDayAppointmentLink,
              AvailDayAppointmentLink.appointment_id == Appointment.id)
        .join(AvailDay,
              AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .join(ActorPlanPeriod,
              ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .join(Person, Person.id == ActorPlanPeriod.person_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .where(Appointment.event_id == event_id_subq)
        .where(Appointment.prep_delete.is_(None))
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
        .distinct()
        .order_by(Person.l_name, Person.f_name)
    )

    rows = session.execute(stmt).mappings().all()
    return [CoWorker(person_id=r["id"], f_name=r["f_name"], l_name=r["l_name"]) for r in rows]
