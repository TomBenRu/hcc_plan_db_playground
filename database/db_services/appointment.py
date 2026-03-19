"""Service-Funktionen für Appointment (Termin / Besetzungseintrag).

Ein Appointment verbindet ein Event mit einem Plan und speichert die
zugewiesenen AvailDays (Akteure), Gäste (JSON-Liste) und Notizen.
Unterstützt Soft-Delete sowie die Abfrage aller Plan-Namen, in denen ein
bestimmtes Event bereits verplant ist.
"""
import datetime
import json
from uuid import UUID

from sqlmodel import select

from .. import schemas, models
from ..database import get_session
from ..models import _utcnow
from ._common import log_function_info


def get(appointment_id: UUID) -> schemas.AppointmentShow:
    with get_session() as session:
        return schemas.AppointmentShow.model_validate(session.get(models.Appointment, appointment_id))


def create(appointment: schemas.AppointmentCreate, plan_id: UUID) -> schemas.AppointmentShow:
    log_function_info()
    with get_session() as session:
        app = models.Appointment(
            event=session.get(models.Event, appointment.event.id),
            plan=session.get(models.Plan, plan_id), notes=appointment.notes)
        session.add(app)
        session.flush()
        for ad in appointment.avail_days:
            app.avail_days.append(session.get(models.AvailDay, ad.id))
        session.flush()
        return schemas.AppointmentShow.model_validate(app)


def update_avail_days(appointment_id: UUID, avail_day_ids: list[UUID]) -> schemas.AppointmentShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.avail_days.clear()
        for aid in avail_day_ids:
            app.avail_days.append(session.get(models.AvailDay, aid))
        session.flush()
        return schemas.AppointmentShow.model_validate(app)


def update_notes(appointment_id: UUID, notes: str) -> schemas.AppointmentShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.notes = notes
        session.flush()
        return schemas.AppointmentShow.model_validate(app)


def update_guests(appointment_id: UUID, guests: list[str]) -> schemas.AppointmentShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.guests = json.dumps(guests)
        session.flush()
        return schemas.AppointmentShow.model_validate(app)


def update_event(appointment_id: UUID, event_id: UUID) -> schemas.AppointmentShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.event = session.get(models.Event, event_id)
        session.flush()
        return schemas.AppointmentShow.model_validate(app)


def delete(appointment_id: UUID) -> schemas.AppointmentShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.prep_delete = _utcnow()
        session.flush()
        return schemas.AppointmentShow.model_validate(app)


def undelete(appointment_id: UUID) -> schemas.AppointmentShow:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.prep_delete = None
        session.flush()
        return schemas.AppointmentShow.model_validate(app)


def get_plan_names_from__event(event_id: UUID) -> dict[str, int]:
    with get_session() as session:
        event = session.get(models.Event, event_id)
        if not event:
            return {}
        plan_counts: dict[str, int] = {}
        for app in event.appointments:
            if not app.prep_delete and not app.plan.prep_delete:
                plan_counts[app.plan.name] = plan_counts.get(app.plan.name, 0) + 1
        return plan_counts