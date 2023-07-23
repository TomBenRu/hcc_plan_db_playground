from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, *, actor_plan_period_id: UUID = None, avail_day_group_id: UUID = None):
        if not actor_plan_period_id and not avail_day_group_id:
            raise AttributeError('Die Parameter "actor_plan_period_id" und "avail_day_group_id" '
                                 'können nicht beide None sein.')
        self.actor_plan_period_id = actor_plan_period_id
        self.avail_day_group_id = avail_day_group_id

        self.created_group: schemas.AvailDayGroupShow | None = None

    def execute(self):
        self.created_group = db_services.AvailDayGroup.create(actor_plan_period_id=self.actor_plan_period_id,
                                                              avail_day_group_id=self.avail_day_group_id)

    def undo(self):
        db_services.AvailDayGroup.delete(self.created_group.id)

    def redo(self):
        self.created_group = db_services.AvailDayGroup.create(self.actor_plan_period_id, self.avail_day_group_id)


class Delete(Command):
    def __init__(self, avail_day_group_id: UUID):
        self.avail_day_group_id = avail_day_group_id
        self.avail_day_group = db_services.AvailDayGroup.get(avail_day_group_id)

    def execute(self):
        db_services.AvailDayGroup.delete(self.avail_day_group_id)

    def undo(self):
        actor_plan_period_id = self.avail_day_group.actor_plan_period.id if self.avail_day_group.actor_plan_period else None
        avail_day_group_id = self.avail_day_group.avail_day_group.id if self.avail_day_group.avail_day_group else None
        db_services.AvailDayGroup.create(
            actor_plan_period_id=actor_plan_period_id,
            avail_day_group_id=avail_day_group_id,
            undo_id=self.avail_day_group_id
        )

    def redo(self):
        db_services.AvailDayGroup.delete(self.avail_day_group_id)


class SetNewParent(Command):
    def __init__(self, avail_day_group_id: UUID, new_parent_id: UUID):
        """new_parent_id ist die id der parent-avail_day_group."""
        self.avail_day_group_id = avail_day_group_id
        self.new_parent_id = new_parent_id
        self.old_parent_id: UUID | None = None

    def execute(self):
        self.old_parent_id = db_services.AvailDayGroup.get(self.avail_day_group_id).avail_day_group.id
        db_services.AvailDayGroup.set_new_parent(self.avail_day_group_id, self.new_parent_id)

    def undo(self):
        db_services.AvailDayGroup.set_new_parent(self.avail_day_group_id, self.old_parent_id)

    def redo(self):
        db_services.AvailDayGroup.set_new_parent(self.avail_day_group_id, self.new_parent_id)


