from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, location_plan_period_id: UUID):
        self.location_plan_period_id = location_plan_period_id
        self.created_cast_group: schemas.CastGroupShow | None = None

    def execute(self):
        self.created_cast_group = db_services.CastGroup.create(location_plan_period_id=self.location_plan_period_id)

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
        db_services.CastGroup.create(location_plan_period_id=self.cast_group.location_plan_period.id,
                                     parent_cast_group_id=self.cast_group.cast_group.id,
                                     undo_cast_group_id=self.cast_group_id)

    def redo(self):
        db_services.CastGroup.delete(self.cast_group_id)


class SetNewParent(Command):
    def __init__(self, cast_group_id: UUID, new_parent_id: UUID | None):
        """new_parent_id ist die id der parent-cast_group."""
        self.cast_group_id = cast_group_id
        self.new_parent_id = new_parent_id
        self.old_parent = db_services.CastGroup.get(cast_group_id).cast_group
        self.old_parent_id: UUID = self.old_parent.id if self.old_parent else None

    def execute(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.new_parent_id)

    def undo(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.old_parent_id)

    def redo(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.new_parent_id)

