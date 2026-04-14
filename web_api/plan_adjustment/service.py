"""Plan-Anpassungs-Service: AvailDay-Reassignment für Übernahme und Tausch."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    CastGroup,
    Event,
    Plan,
)
from web_api.availability.service import create_avail_day, find_avail_day


def reassign_appointment(
    session: Session,
    appointment_id: uuid.UUID,
    old_person_id: uuid.UUID,
    new_person_id: uuid.UUID,
) -> None:
    """Verschiebt einen Appointment von old_person zu new_person via AvailDay-Reassignment.

    Ablauf:
    1. Alten AvailDayAppointmentLink des old_person finden und löschen.
    2. ActorPlanPeriod des new_person in der selben PlanPeriod laden.
    3. Bestehenden AvailDay suchen oder neuen anlegen.
    4. Neuen AvailDayAppointmentLink erstellen.
    """
    # 1. Alten Link + AvailDay des old_person finden
    old_link_row = session.execute(
        sa_select(AvailDayAppointmentLink, AvailDay)
        .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
        .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
        .where(AvailDayAppointmentLink.appointment_id == appointment_id)
        .where(ActorPlanPeriod.person_id == old_person_id)
    ).first()

    if old_link_row is not None:
        old_link, old_avail_day = old_link_row
        session.delete(old_link)
        session.flush()

    # 2. Appointment-Kontext laden (Event-Datum + TimeOfDay + CastGroup)
    appt_row = session.execute(
        sa_select(
            Appointment.plan_id,
            Event.date.label("event_date"),
            Event.time_of_day_id,
            Event.cast_group_id,
            Plan.plan_period_id,
        )
        .select_from(Appointment)
        .join(Event, Event.id == Appointment.event_id)
        .join(Plan, Plan.id == Appointment.plan_id)
        .where(Appointment.id == appointment_id)
    ).mappings().first()

    if appt_row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Termin nicht gefunden")

    plan_period_id: uuid.UUID = appt_row["plan_period_id"]
    event_date = appt_row["event_date"]
    time_of_day_id: uuid.UUID = appt_row["time_of_day_id"]
    cast_group_id: uuid.UUID = appt_row["cast_group_id"]

    # 3. ActorPlanPeriod des new_person in derselben PlanPeriod finden
    new_app = session.execute(
        sa_select(ActorPlanPeriod)
        .where(ActorPlanPeriod.plan_period_id == plan_period_id)
        .where(ActorPlanPeriod.person_id == new_person_id)
    ).scalars().first()

    if new_app is None:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Neue Person hat keine Verfügbarkeitsperiode in dieser Planperiode.",
        )

    # 4. Bestehenden AvailDay suchen oder neuen anlegen
    avail_day = find_avail_day(session, new_app.id, event_date, time_of_day_id)
    if avail_day is None:
        avail_day = create_avail_day(session, new_app.id, event_date, time_of_day_id)

    # 5. Neuen Link anlegen
    new_link = AvailDayAppointmentLink(
        avail_day_id=avail_day.id,
        appointment_id=appointment_id,
    )
    session.add(new_link)
    session.flush()

    # 6. fixed_cast der CastGroup löschen — manuelle Zuweisung überschreibt den Constraint;
    #    andernfalls meldet validate_plan einen Fehler, weil die neue Person nicht im
    #    fixed_cast-Ausdruck enthalten ist.
    cast_group = session.get(CastGroup, cast_group_id)
    if cast_group is not None and cast_group.fixed_cast is not None:
        cast_group.fixed_cast = None
        session.flush()


def swap_appointments(
    session: Session,
    appt_a_id: uuid.UUID,
    person_a_id: uuid.UUID,
    appt_b_id: uuid.UUID,
    person_b_id: uuid.UUID,
) -> None:
    """Tauscht zwei Appointments zwischen zwei Personen.

    Löscht beide alten Links zuerst (flush), dann legt neue an — verhindert
    UniqueConstraint-Konflikte falls beide AvailDays identisch wären.
    """
    # Alte Links finden
    def _find_link(appointment_id: uuid.UUID, person_id: uuid.UUID):
        return session.execute(
            sa_select(AvailDayAppointmentLink)
            .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
            .join(ActorPlanPeriod, ActorPlanPeriod.id == AvailDay.actor_plan_period_id)
            .where(AvailDayAppointmentLink.appointment_id == appointment_id)
            .where(ActorPlanPeriod.person_id == person_id)
        ).scalars().first()

    link_a = _find_link(appt_a_id, person_a_id)
    link_b = _find_link(appt_b_id, person_b_id)

    if link_a is not None:
        session.delete(link_a)
    if link_b is not None:
        session.delete(link_b)
    session.flush()

    # Neu-Zuordnung: A → person_b, B → person_a
    reassign_appointment(session, appt_a_id, person_a_id, person_b_id)
    reassign_appointment(session, appt_b_id, person_b_id, person_a_id)
