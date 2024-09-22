import datetime
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, appointment: schemas.AppointmentCreate, plan_id: UUID):
        self.appointment = appointment
        self.plan_id = plan_id
        self.appointment_created: schemas.AppointmentShow | None = None

    def execute(self):
        self.appointment_created = db_services.Appointment.create(self.appointment, self.plan_id)

    def undo(self):
        db_services.Appointment.delete(self.appointment_created.id)

    def redo(self):
        db_services.Appointment.undelete(self.appointment_created.id)


class UpdateAvailDays(Command):
    def __init__(self, appointment_id: UUID, avail_day_ids: list[UUID]):
        self.appointment_id = appointment_id
        self.avail_day_ids = avail_day_ids
        self.appointment = db_services.Appointment.get(self.appointment_id)
        self.updated_appointment: schemas.AppointmentShow | None = None

    def execute(self):
        self.updated_appointment = db_services.Appointment.update_avail_days(self.appointment_id, self.avail_day_ids)

    def undo(self):
        db_services.Appointment.update_avail_days(self.appointment_id, [avd.id for avd in self.appointment.avail_days])

    def redo(self):
        db_services.Appointment.update_avail_days(self.appointment_id, self.avail_day_ids)


class UpdateCurrEvent(Command):
    def __init__(self, appointment: schemas.Appointment, new_date: datetime.date, new_time_of_day_id: UUID):
        self.appointment = appointment
        self.new_date = new_date
        self.new_time_of_day_id = new_time_of_day_id
        self.updated_event: schemas.EventShow | None = None

    def execute(self):
        self.updated_event = db_services.Event.update_time_of_day_and_date(
            self.appointment.event.id, self.new_time_of_day_id, self.new_date)

    def undo(self):
        db_services.Event.update_time_of_day_and_date(
            self.appointment.event.id, self.appointment.event.time_of_day.id, self.appointment.event.date)

    def redo(self):
        db_services.Event.update_time_of_day_and_date(
            self.appointment.event.id, self.new_time_of_day_id, self.new_date)


class UpdateEvent(Command):
    def __init__(self, appointment: schemas.Appointment, new_event_id: UUID):
        self.appointment = appointment
        self.new_event_id = new_event_id
        self.updated_appointment: schemas.AppointmentShow | None = None

    def execute(self):
        self.updated_appointment = db_services.Appointment.update_event(self.appointment.id, self.new_event_id)

    def undo(self):
        db_services.Appointment.update_event(self.appointment.id, self.appointment.event.id)

    def redo(self):
        db_services.Appointment.update_event(self.appointment.id, self.new_event_id)


class UpdateGuests(Command):
    def __init__(self, appointment_id: UUID, guests: list[str]):
        self.appointment_id = appointment_id
        self.guests = guests
        self.appointment = db_services.Appointment.get(self.appointment_id)
        self.updated_appointment: schemas.AppointmentShow | None = None

    def execute(self):
        self.updated_appointment = db_services.Appointment.update_guests(self.appointment_id, self.guests)

    def undo(self):
        db_services.Appointment.update_guests(self.appointment_id, self.appointment.guests)

    def redo(self):
        db_services.Appointment.update_guests(self.appointment_id, self.guests)
