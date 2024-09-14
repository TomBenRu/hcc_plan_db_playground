from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Delete(Command):
    def __init__(self, plan_period_id: UUID):
        self.plan_period_id = plan_period_id

    def execute(self):
        db_services.PlanPeriod.delete(self.plan_period_id)

    def undo(self):
        db_services.PlanPeriod.undelete(self.plan_period_id)

    def redo(self):
        db_services.PlanPeriod.delete(self.plan_period_id)


class UpdateNotes(Command):
    def __init__(self, plan_period_id, notes: str):
        self.plan_period_id = plan_period_id
        self.plan_period = db_services.PlanPeriod.get(plan_period_id)
        self.updated_plan_period: schemas.PlanPeriodShow | None = None
        self.notes = notes

    def execute(self):
        self.updated_plan_period = db_services.PlanPeriod.update_notes(self.plan_period_id, self.notes)

    def undo(self):
        db_services.PlanPeriod.update_notes(self.plan_period_id, self.plan_period.notes)

    def redo(self):
        db_services.PlanPeriod.update_notes(self.plan_period_id, self.notes)
