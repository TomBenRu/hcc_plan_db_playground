from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, *, location_plan_period_id: UUID = None, event_group_id: UUID = None):
        if not location_plan_period_id and not event_group_id:
            raise AttributeError('Die Parameter "actor_plan_period_id" und "avail_day_group_id" '
                                 'können nicht beide None sein.')
        self.location_plan_period_id = location_plan_period_id
        self.event_group_id = event_group_id

        self.created_group: schemas.EventGroupShow | None = None

    def execute(self):
        self.created_group = db_services.EventGroup.create(location_plan_period_id=self.location_plan_period_id,
                                                           event_group_id=self.event_group_id)

    def undo(self):
        db_services.EventGroup.delete(self.created_group.id)

    def redo(self):
        self.created_group = db_services.EventGroup.create(self.location_plan_period_id, self.event_group_id)


class Delete(Command):
    def __init__(self, event_group_id: UUID):
        self.event_group_id = event_group_id
        self.event_group = db_services.EventGroup.get(event_group_id)
        self.parent_event_group_id: UUID | None = None
        self.parent_nr_event_groups: int | None = None

    def execute(self):
        db_services.EventGroup.delete(self.event_group_id)

        # Um Inkonsistenzen zu vermeiden:
        parent_event_groups = db_services.EventGroup.get_child_groups_from__parent_group(self.event_group.event_group.id)
        parent_nr_event_groups = self.event_group.event_group.nr_event_groups
        if parent_nr_event_groups and parent_nr_event_groups > len(parent_event_groups):
            self.parent_nr_event_groups = parent_nr_event_groups
            db_services.EventGroup.update_nr_event_groups(self.event_group.event_group.id, None)

    def undo(self):
        location_plan_period_id = (self.event_group.location_plan_period.id
                                   if self.event_group.location_plan_period else None)
        event_group_id = self.event_group.event_group.id if self.event_group.event_group else None
        db_services.EventGroup.create(
            location_plan_period_id=location_plan_period_id,
            event_group_id=event_group_id,
            undo_id=self.event_group_id
        )
        if self.parent_nr_event_groups:
            db_services.EventGroup.update_nr_event_groups(self.event_group.event_group.id, self.parent_nr_event_groups)

    def redo(self):
        db_services.EventGroup.delete(self.event_group_id)

        parent_event_groups = db_services.EventGroup.get_child_groups_from__parent_group(
            self.event_group.event_group.id)
        parent_nr_event_groups = self.event_group.event_group.nr_event_groups
        if parent_nr_event_groups and parent_nr_event_groups > len(parent_event_groups):
            self.parent_nr_event_groups = parent_nr_event_groups
            db_services.EventGroup.update_nr_event_groups(self.event_group.event_group.id, None)


class UpdateNrEventGroups(Command):
    def __init__(self, event_group_id: UUID, nr_event_groups: int | None):
        self.event_group_id = event_group_id
        self.nr_event_groups = nr_event_groups
        self.nr_event_groups_old: int | None = None

    def execute(self):
        event_group = db_services.EventGroup.get(self.event_group_id)
        self.nr_event_groups_old = event_group.nr_event_groups
        db_services.EventGroup.update_nr_event_groups(self.event_group_id, self.nr_event_groups)

    def undo(self):
        db_services.EventGroup.update_nr_event_groups(self.event_group_id, self.nr_event_groups_old)

    def redo(self):
        db_services.EventGroup.update_nr_event_groups(self.event_group_id, self.nr_event_groups)


class UpdateVariationWeight(Command):
    def __init__(self, event_group_id: UUID, variation_weight: int):
        self.event_group_id = event_group_id
        self.variation_weight = variation_weight
        self.variation_weight_old: int | None = None

    def execute(self):
        event_group = db_services.EventGroup.get(self.event_group_id)
        self.variation_weight_old = event_group.variation_weight
        db_services.EventGroup.update_variation_weight(self.event_group_id, self.variation_weight)

    def undo(self):
        db_services.EventGroup.update_variation_weight(self.event_group_id, self.variation_weight_old)

    def redo(self):
        db_services.EventGroup.update_variation_weight(self.event_group_id, self.variation_weight)


class SetNewParent(Command):
    def __init__(self, event_group_id: UUID, new_parent_id: UUID):
        """new_parent_id ist die id der parent-avail_day_group."""
        self.event_group_id = event_group_id
        self.new_parent_id = new_parent_id
        self.old_parent_id: UUID | None = None
        self.old_parent_nr_event_groups: int | None = None

    def execute(self):
        old_parent = db_services.EventGroup.get(self.event_group_id).event_group

        db_services.EventGroup.set_new_parent(self.event_group_id, self.new_parent_id)

        # Um Inkonsistenzen zu vermeiden:
        old_parent_childs = db_services.EventGroup.get_child_groups_from__parent_group(old_parent.id)
        if old_parent.nr_event_groups and old_parent.nr_event_groups > len(old_parent_childs):
            self.old_parent_nr_event_groups = old_parent.nr_event_groups
            db_services.EventGroup.update_nr_event_groups(old_parent.id, None)
        self.old_parent_id = old_parent.id

    def undo(self):
        db_services.EventGroup.set_new_parent(self.event_group_id, self.old_parent_id)
        if self.old_parent_nr_event_groups:
            db_services.EventGroup.update_nr_event_groups(self.old_parent_id, self.old_parent_nr_event_groups)

    def redo(self):
        old_parent = db_services.EventGroup.get(self.event_group_id).eventgroup

        db_services.EventGroup.set_new_parent(self.event_group_id, self.new_parent_id)

        old_parent_childs = db_services.EventGroup.get_child_groups_from__parent_group(old_parent.id)
        if old_parent.nr_event_groups and old_parent.nr_event_groups > len(old_parent_childs):
            self.old_parent_nr_event_groups = old_parent.nr_event_groups
            db_services.EventGroup.update_nr_event_groups(old_parent.id, None)