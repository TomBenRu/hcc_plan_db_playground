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

