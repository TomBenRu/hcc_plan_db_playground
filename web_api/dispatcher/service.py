"""Service-Schicht für die Dispatcher-Plan-Ansicht.

Spiegelt `web_api/employees/service.py`, filtert jedoch auf Team-Ebene
(PlanPeriod.team_id) statt auf Person-Ebene (ActorPlanPeriod.person_id).
"""

import uuid
from dataclasses import dataclass
from datetime import date

from sqlalchemy import func
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    Appointment,
    AvailDayAppointmentLink,
    CastGroup,
    Event,
    LocationOfWork,
    LocationPlanPeriod,
    Plan,
    PlanPeriod,
    Team,
    TimeOfDay,
)
from web_api.employees.service import CalendarEvent, location_color


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
) -> list[CalendarEvent]:
    """Alle Appointments der angegebenen Teams als CalendarEvents."""
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
        guests_count = len(r["guests"] or [])
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