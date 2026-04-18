"""Command-Klassen für Appointment (Dienstplan-Eintrag / Besetzung).

Kapselt alle Änderungen an einem Appointment: Erstellen, Löschen (Soft-Delete),
sowie das Ändern von zugewiesenen AvailDays, Notizen, Gästen und dem verknüpften
Event. Viele Klassen implementieren `__str__` für menschenlesbare Undo-Historie
(Standort, Datum, Tageszeit werden im Text angezeigt).
"""
import datetime
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import appointment as api_appointment, event as api_event
from tools.helper_functions import date_to_string


class Create(Command):
    def __init__(self, appointment: schemas.AppointmentCreate, plan_id: UUID):
        super().__init__()
        self.appointment = appointment
        self.plan_id = plan_id
        self.appointment_created: schemas.AppointmentShow | None = None

    def execute(self):
        self.appointment_created = api_appointment.create(self.appointment, self.plan_id)

    def _undo(self):
        api_appointment.delete(self.appointment_created.id)

    def _redo(self):
        api_appointment.undelete(self.appointment_created.id)


class CreateBulk(Command):
    """Erstellt alle Appointments einer Plan-Version in einer einzigen DB-Session."""

    def __init__(self, appointments: list[schemas.AppointmentCreate], plan_id: UUID):
        super().__init__()
        self.appointments = appointments
        self.plan_id = plan_id
        self.created_ids: list[UUID] = []

    def execute(self):
        self.created_ids = api_appointment.create_bulk(self.appointments, self.plan_id)

    def _undo(self):
        api_appointment.delete_bulk(self.created_ids)

    def _redo(self):
        api_appointment.undelete_bulk(self.created_ids)


class UpdateAvailDays(Command):
    def __init__(self, appointment_id: UUID, avail_day_ids: list[UUID],
                 appointment: schemas.Appointment = None):
        super().__init__()
        self.appointment_id = appointment_id
        self.avail_day_ids = avail_day_ids
        self.appointment = appointment if appointment is not None else db_services.Appointment.get(self.appointment_id)

    def execute(self):
        api_appointment.update_avail_days(self.appointment_id, self.avail_day_ids)

    def _undo(self):
        api_appointment.update_avail_days(self.appointment_id, [avd.id for avd in self.appointment.avail_days])

    def _redo(self):
        api_appointment.update_avail_days(self.appointment_id, self.avail_day_ids)

    def __str__(self) -> str:
        try:
            event_date = self.appointment.event.date
            event_time_of_day = self.appointment.event.time_of_day.name
            event_location = self.appointment.event.location_plan_period.location_of_work.name_an_city
            cast_new = sorted(avd.actor_plan_period.person.full_name for avd in self.appointment.avail_days)
            cast_old = sorted(avd.actor_plan_period.person.full_name for avd in self.appointment.avail_days)

            return (f"Verfügbarkeitstage ändern für\n"
                    f"{event_location} - {date_to_string(event_date)} ({event_time_of_day}): {cast_old} → {cast_new}")
        except (AttributeError, TypeError):
            return "Verfügbarkeitstage ändern"


class UpdateNotes(Command):
    def __init__(self, appointment: schemas.Appointment, notes: str):
        super().__init__()
        self.appointment = appointment
        self.notes = notes

    def execute(self):
        api_appointment.update_notes(self.appointment.id, self.notes)

    def _undo(self):
        api_appointment.update_notes(self.appointment.id, self.appointment.notes)

    def _redo(self):
        api_appointment.update_notes(self.appointment.id, self.notes)

    def __str__(self) -> str:
        try:
            event_date = self.appointment.event.date
            event_time_of_day = self.appointment.event.time_of_day.name
            event_location = self.appointment.event.location_plan_period.location_of_work.name_an_city
            if self.notes and len(self.notes) > 30:
                note_preview = self.notes[:30] + "..."
            else:
                note_preview = self.notes or "(leer)"
            return (f"Notiz ändern für\n"
                    f"{event_location} - {date_to_string(event_date)} ({event_time_of_day}):\n"
                    f"{note_preview}")
        except (AttributeError, TypeError):
            return "Notiz ändern"


class UpdateCurrEvent(Command):
    def __init__(self, appointment: schemas.Appointment, new_date: datetime.date, new_time_of_day_id: UUID):
        super().__init__()
        self.appointment = appointment
        self.new_date = new_date
        self.new_time_of_day_id = new_time_of_day_id
        self.updated_event: schemas.EventShow | None = None

    def execute(self):
        self.updated_event = api_event.update_time_of_day_and_date(
            self.appointment.event.id, self.new_time_of_day_id, self.new_date)

    def _undo(self):
        api_event.update_time_of_day_and_date(
            self.appointment.event.id, self.appointment.event.time_of_day.id, self.appointment.event.date)

    def _redo(self):
        api_event.update_time_of_day_and_date(
            self.appointment.event.id, self.new_time_of_day_id, self.new_date)

    def __str__(self) -> str:
        try:
            event_date_old = self.appointment.event.date
            event_date_new = self.new_date
            event_time_of_day_old = self.appointment.event.time_of_day.name
            event_time_of_day_new = self.updated_event.time_of_day.name
            event_location = self.appointment.event.location_plan_period.location_of_work.name_an_city
            return (f"Termin verschieben für\n"
                    f"{event_location} - {date_to_string(event_date_old)} ({event_time_of_day_old}) "
                    f"→ {date_to_string(event_date_new)} ({event_time_of_day_new})")
        except (AttributeError, TypeError):
            return "Termin verschieben"


class UpdateEvent(Command):
    def __init__(self, appointment: schemas.Appointment, new_event_id: UUID):
        super().__init__()
        self.appointment = appointment
        self.new_event_id = new_event_id

    def execute(self):
        api_appointment.update_event(self.appointment.id, self.new_event_id)

    def _undo(self):
        api_appointment.update_event(self.appointment.id, self.appointment.event.id)

    def _redo(self):
        api_appointment.update_event(self.appointment.id, self.new_event_id)


class UpdateGuests(Command):
    def __init__(self, appointment_id: UUID, guests: list[str],
                 appointment: schemas.Appointment = None):
        super().__init__()
        self.appointment_id = appointment_id
        self.guests = guests
        self.appointment = appointment if appointment is not None else db_services.Appointment.get(self.appointment_id)

    def execute(self):
        api_appointment.update_guests(self.appointment_id, self.guests)

    def _undo(self):
        api_appointment.update_guests(self.appointment_id, self.appointment.guests)

    def _redo(self):
        api_appointment.update_guests(self.appointment_id, self.guests)

    def __str__(self) -> str:
        try:
            event_date = self.appointment.event.date
            event_time_of_day = self.appointment.event.time_of_day.name
            event_location = self.appointment.event.location_plan_period.location_of_work.name_an_city
            new_guests = ', '.join(self.guests) if self.guests else '(keine)'
            old_guests = ', '.join(self.appointment.guests) if self.appointment.guests else '(keine)'
            return (f"Gäste ändern für\n"
                    f"{event_location} - "
                    f"{date_to_string(event_date)} ({event_time_of_day}): {old_guests} → {new_guests}")
        except (AttributeError, TypeError):
            return "Gäste ändern"
