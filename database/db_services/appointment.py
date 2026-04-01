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


def update_avail_days(appointment_id: UUID, avail_day_ids: list[UUID]) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.avail_days.clear()
        for aid in avail_day_ids:
            app.avail_days.append(session.get(models.AvailDay, aid))
        session.flush()


def update_notes(appointment_id: UUID, notes: str) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.notes = notes
        session.flush()


def update_guests(appointment_id: UUID, guests: list[str]) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.guests = json.dumps(guests)
        session.flush()


def update_event(appointment_id: UUID, event_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.event = session.get(models.Event, event_id)
        session.flush()


def delete(appointment_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.prep_delete = _utcnow()
        session.flush()


def undelete(appointment_id: UUID) -> None:
    log_function_info()
    with get_session() as session:
        app = session.get(models.Appointment, appointment_id)
        app.prep_delete = None
        session.flush()


def create_bulk(appointments: list[schemas.AppointmentCreate], plan_id: UUID) -> list[UUID]:
    """Erstellt alle Appointments in einer einzigen Session/Transaktion.

    Gibt nur die UUIDs zurück (kein model_validate-Overhead).
    Da Appointment.id per uuid4() Python-seitig generiert wird, ist kein
    Zwischens-flush() für die M2M-Beziehungen nötig.
    """
    log_function_info()
    with get_session() as session:
        plan = session.get(models.Plan, plan_id)
        created_ids: list[UUID] = []
        for appointment in appointments:
            app = models.Appointment(
                event=session.get(models.Event, appointment.event.id),
                plan=plan,
                notes=appointment.notes,
            )
            session.add(app)
            for ad in appointment.avail_days:
                app.avail_days.append(session.get(models.AvailDay, ad.id))
            created_ids.append(app.id)
        session.flush()
        return created_ids


def delete_bulk(appointment_ids: list[UUID]) -> None:
    log_function_info()
    now = _utcnow()
    with get_session() as session:
        for app_id in appointment_ids:
            app = session.get(models.Appointment, app_id)
            app.prep_delete = now


def undelete_bulk(appointment_ids: list[UUID]) -> None:
    log_function_info()
    with get_session() as session:
        for app_id in appointment_ids:
            app = session.get(models.Appointment, app_id)
            app.prep_delete = None


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