from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Delete(Command):
    def __init__(self, plan_period_id: UUID):
        self.plan_period_id = plan_period_id

    def execute(self):
        db_services.PlanPeriod.delete(self.plan_period_id)

    def undo(self):
        db_services.PlanPeriod.undelete(self.plan_period_id)

    def redo(self):
        db_services.PlanPeriod.delete(self.plan_period_id)
