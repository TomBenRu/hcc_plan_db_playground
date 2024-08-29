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
