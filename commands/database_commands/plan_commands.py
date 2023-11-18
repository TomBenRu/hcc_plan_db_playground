from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, plan_period_id: UUID, name: str):
        self.plan_period_id = plan_period_id
        self.name = name
        self.plan: schemas.PlanShow | None = None

    def execute(self):
        self.plan = db_services.Plan.create(self.plan_period_id, self.name)

    def undo(self):
        db_services.Plan.delete(self.plan.id)

    def redo(self):
        db_services.Plan.undelete(self.plan.id)
