"""Read-only Info-Card fuer einen Einsatzort.

Wird vom Modal verwendet, das beim Klick auf die EINSATZORT-Karte im Termin-Detail
oeffnet (Dispatcher- und Mitarbeiter-Sicht).
"""

import uuid
from dataclasses import dataclass
from datetime import date, time
from urllib.parse import quote

from sqlalchemy import select as sa_select
from sqlmodel import Session

from database.models import (
    ActorPlanPeriod,
    Address,
    Appointment,
    AvailDay,
    AvailDayAppointmentLink,
    Event,
    LocationOfWork,
    LocationPlanPeriod,
    Person,
    Plan,
    TimeOfDay,
)
from web_api.common import location_display_name


@dataclass
class UpcomingAppointment:
    appointment_id: uuid.UUID
    event_date: date
    time_of_day_name: str | None
    time_start: time | None
    time_end: time | None
    cast_names: list[str]


@dataclass
class LocationInfoCard:
    location_id: uuid.UUID
    name: str
    display_name: str
    color: str
    address_lines: list[str]
    maps_url: str | None
    notes: str | None
    upcoming: list[UpcomingAppointment]
    is_dispatcher_view: bool


def get_info_card_data(
    session: Session,
    *,
    location_id: uuid.UUID,
    viewer_person_id: uuid.UUID,
    color: str,
    is_dispatcher: bool,
    exclude_appointment_id: uuid.UUID | None = None,
    limit: int = 5,
) -> LocationInfoCard | None:
    """Laedt Location-Stammdaten + Adresse + naechste Termine.

    Mitarbeiter: nur Termine, in denen die Person eingeteilt ist.
    Dispatcher: alle Termine + Cast-Namen pro Termin (Batch-Query, kein N+1).
    Project-Scope: Location muss zum selben Projekt wie der Viewer gehoeren.
    """
    project_id = session.execute(
        sa_select(Person.project_id).where(Person.id == viewer_person_id)
    ).scalar_one_or_none()
    if project_id is None:
        return None

    loc = session.execute(
        sa_select(
            LocationOfWork.id,
            LocationOfWork.name,
            LocationOfWork.notes,
            Address.street,
            Address.postal_code,
            Address.city,
        )
        .outerjoin(Address, Address.id == LocationOfWork.address_id)
        .where(LocationOfWork.id == location_id)
        .where(LocationOfWork.project_id == project_id)
        .where(LocationOfWork.prep_delete.is_(None))
    ).mappings().first()
    if loc is None:
        return None

    address_lines: list[str] = []
    maps_parts: list[str] = [loc["name"]]
    if loc["street"]:
        address_lines.append(loc["street"])
        maps_parts.append(loc["street"])
    plz_city = " ".join(p for p in (loc["postal_code"], loc["city"]) if p)
    if plz_city:
        address_lines.append(plz_city)
        maps_parts.append(plz_city)
    maps_url: str | None = None
    if address_lines:
        maps_url = (
            "https://www.google.com/maps/search/?api=1&query="
            + quote(", ".join(maps_parts))
        )

    today = date.today()
    base = (
        sa_select(
            Appointment.id.label("appointment_id"),
            Event.date.label("event_date"),
            TimeOfDay.name.label("tod_name"),
            TimeOfDay.start.label("time_start"),
            TimeOfDay.end.label("time_end"),
        )
        .join(Event, Event.id == Appointment.event_id)
        .join(
            LocationPlanPeriod,
            LocationPlanPeriod.id == Event.location_plan_period_id,
        )
        .join(TimeOfDay, TimeOfDay.id == Event.time_of_day_id, isouter=True)
        .join(Plan, Plan.id == Appointment.plan_id)
        .where(LocationPlanPeriod.location_of_work_id == location_id)
        .where(Event.date >= today)
        .where(Appointment.prep_delete.is_(None))
        .where(Plan.is_binding.is_(True))
        .where(Plan.prep_delete.is_(None))
    )
    if exclude_appointment_id is not None:
        base = base.where(Appointment.id != exclude_appointment_id)

    if not is_dispatcher:
        base = (
            base.join(
                AvailDayAppointmentLink,
                AvailDayAppointmentLink.appointment_id == Appointment.id,
            )
            .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
            .join(
                ActorPlanPeriod,
                ActorPlanPeriod.id == AvailDay.actor_plan_period_id,
            )
            .where(ActorPlanPeriod.person_id == viewer_person_id)
        )

    base = base.order_by(Event.date, TimeOfDay.start).limit(limit)
    rows = session.execute(base).mappings().all()

    cast_by_appt: dict[uuid.UUID, list[str]] = {}
    if is_dispatcher and rows:
        appt_ids = [r["appointment_id"] for r in rows]
        cast_rows = session.execute(
            sa_select(
                AvailDayAppointmentLink.appointment_id,
                Person.f_name,
                Person.l_name,
            )
            .join(AvailDay, AvailDay.id == AvailDayAppointmentLink.avail_day_id)
            .join(
                ActorPlanPeriod,
                ActorPlanPeriod.id == AvailDay.actor_plan_period_id,
            )
            .join(Person, Person.id == ActorPlanPeriod.person_id)
            .where(AvailDayAppointmentLink.appointment_id.in_(appt_ids))
            .distinct()
            .order_by(Person.l_name, Person.f_name)
        ).all()
        for appt_id, f, l in cast_rows:
            full = " ".join(p for p in (f, l) if p) or "?"
            cast_by_appt.setdefault(appt_id, []).append(full)

    upcoming = [
        UpcomingAppointment(
            appointment_id=r["appointment_id"],
            event_date=r["event_date"],
            time_of_day_name=r["tod_name"],
            time_start=r["time_start"],
            time_end=r["time_end"],
            cast_names=cast_by_appt.get(r["appointment_id"], []),
        )
        for r in rows
    ]

    return LocationInfoCard(
        location_id=loc["id"],
        name=loc["name"],
        display_name=location_display_name(loc["name"], loc["city"]),
        color=color,
        address_lines=address_lines,
        maps_url=maps_url,
        notes=loc["notes"],
        upcoming=upcoming,
        is_dispatcher_view=is_dispatcher,
    )
