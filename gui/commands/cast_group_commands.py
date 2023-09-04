from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, location_plan_period_id: UUID):
        self.location_plan_period_id = location_plan_period_id
        self.created_cast_group: schemas.CastGroupShow | None = None

    def execute(self):
        self.created_cast_group = db_services.CastGroup.create(self.location_plan_period_id)

    def undo(self):
        db_services.CastGroup.delete(self.created_cast_group.id)

    def redo(self):
        self.created_cast_group = db_services.CastGroup.create(self.location_plan_period_id)


class Delete(Command):
    def __init__(self, cast_group_id: UUID):
        self.cast_group_id = cast_group_id
        self.cast_group = db_services.CastGroup.get(cast_group_id)

    def execute(self):
        db_services.CastGroup.delete(self.cast_group_id)

    def undo(self):
        db_services.CastGroup.create(self.cast_group.location_plan_period.id, self.cast_group.cast_group.id)

    def redo(self):
        db_services.CastGroup.delete(self.cast_group_id)
