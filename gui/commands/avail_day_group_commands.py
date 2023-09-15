from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    """Die seltsame Benennung der Parameter ist der gemeinsamen DlgGroupMode-Klasse geschuldet."""
    def __init__(self, *, loc_act_plan_period_id: UUID = None, event_avail_day_group_id: UUID = None):
        """Die Parameter 'loc_act_plan_period_id' und 'event_avail_day_group_id' können nicht beide None sein."""
        if not loc_act_plan_period_id and not event_avail_day_group_id:
            raise AttributeError('Die Parameter "actor_plan_period_id" und "avail_day_group_id" '
                                 'können nicht beide None sein.')
        self.actor_plan_period_id = loc_act_plan_period_id
        self.avail_day_group_id = event_avail_day_group_id

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
        self.parent_avail_day_group_id: UUID | None = None
        self.parent_nr_avail_day_groups: int | None = None

    def execute(self):
        db_services.AvailDayGroup.delete(self.avail_day_group_id)

        # Um Inkonsistenzen zu vermeiden:
        parent_avd_groups = db_services.AvailDayGroup.get_child_groups_from__parent_group(self.avail_day_group.avail_day_group.id)
        parent_nr_avail_day_groups = self.avail_day_group.avail_day_group.nr_avail_day_groups
        if parent_nr_avail_day_groups and parent_nr_avail_day_groups  > len(parent_avd_groups):
            self.parent_nr_avail_day_groups = parent_nr_avail_day_groups
            db_services.AvailDayGroup.update_nr_avail_day_groups(self.avail_day_group.avail_day_group.id, None)

    def undo(self):
        actor_plan_period_id = (self.avail_day_group.actor_plan_period.id
                                if self.avail_day_group.actor_plan_period else None)
        avail_day_group_id = self.avail_day_group.avail_day_group.id if self.avail_day_group.avail_day_group else None
        db_services.AvailDayGroup.create(
            actor_plan_period_id=actor_plan_period_id,
            avail_day_group_id=avail_day_group_id,
            undo_id=self.avail_day_group_id
        )
        if self.parent_nr_avail_day_groups:
            db_services.AvailDayGroup.update_nr_avail_day_groups(self.avail_day_group.avail_day_group.id,
                                                                 self.parent_nr_avail_day_groups)

    def redo(self):
        db_services.AvailDayGroup.delete(self.avail_day_group_id)

        parent_avd_groups = db_services.AvailDayGroup.get_child_groups_from__parent_group(
            self.avail_day_group.avail_day_group.id)
        parent_nr_avail_day_groups = self.avail_day_group.avail_day_group.nr_avail_day_groups
        if parent_nr_avail_day_groups and parent_nr_avail_day_groups > len(parent_avd_groups):
            self.parent_nr_avail_day_groups = parent_nr_avail_day_groups
            db_services.AvailDayGroup.update_nr_avail_day_groups(self.avail_day_group.avail_day_group.id, None)


class UpdateNrAvailDayGroups(Command):
    def __init__(self, avail_day_group_id: UUID, nr_avail_day_groups: int | None):
        self.avail_day_group_id= avail_day_group_id
        self.nr_avail_day_groups = nr_avail_day_groups
        self.nr_avail_day_groups_old: int | None = None

    def execute(self):
        avail_day_group = db_services.AvailDayGroup.get(self.avail_day_group_id)
        self.nr_avail_day_groups_old = avail_day_group.nr_avail_day_groups
        db_services.AvailDayGroup.update_nr_avail_day_groups(self.avail_day_group_id, self.nr_avail_day_groups)

    def undo(self):
        db_services.AvailDayGroup.update_nr_avail_day_groups(self.avail_day_group_id, self.nr_avail_day_groups_old)

    def redo(self):
        db_services.AvailDayGroup.update_nr_avail_day_groups(self.avail_day_group_id, self.nr_avail_day_groups)


class UpdateVariationWeight(Command):
    def __init__(self, avail_day_group_id: UUID, variation_weight: int):
        self.avail_day_group_id= avail_day_group_id
        self.variation_weight = variation_weight
        self.variation_weight_old: int | None = None

    def execute(self):
        avail_day_group = db_services.AvailDayGroup.get(self.avail_day_group_id)
        self.variation_weight_old = avail_day_group.variation_weight
        db_services.AvailDayGroup.update_variation_weight(self.avail_day_group_id, self.variation_weight)

    def undo(self):
        db_services.AvailDayGroup.update_variation_weight(self.avail_day_group_id, self.variation_weight_old)

    def redo(self):
        db_services.AvailDayGroup.update_variation_weight(self.avail_day_group_id, self.variation_weight)


class UpdateMandatoryNrAvailDayGroups(Command):
    def __init__(self, avail_day_group_id: UUID, mandatory_nr_avail_day_groups: int | None):
        self.avail_day_group_id = avail_day_group_id
        self.mandatory_nr_avail_day_groups = mandatory_nr_avail_day_groups
        self.mandatory_nr_avail_day_groups_old = db_services.AvailDayGroup.get(avail_day_group_id).mandatory_nr_avail_day_groups

    def execute(self):
        db_services.AvailDayGroup.update_mandatory_nr_avail_day_groups(
            self.avail_day_group_id, self.mandatory_nr_avail_day_groups)

    def undo(self):
        db_services.AvailDayGroup.update_mandatory_nr_avail_day_groups(
            self.avail_day_group_id, self.mandatory_nr_avail_day_groups_old)

    def redo(self):
        db_services.AvailDayGroup.update_mandatory_nr_avail_day_groups(
            self.avail_day_group_id, self.mandatory_nr_avail_day_groups)


class SetNewParent(Command):
    def __init__(self, avail_day_group_id: UUID, new_parent_id: UUID):
        """new_parent_id ist die id der parent-avail_day_group."""
        self.avail_day_group_id = avail_day_group_id
        self.new_parent_id = new_parent_id
        self.old_parent_id: UUID | None = None
        self.old_parent_nr_avail_day_groups: int | None = None

    def execute(self):
        old_parent = db_services.AvailDayGroup.get(self.avail_day_group_id).avail_day_group

        db_services.AvailDayGroup.set_new_parent(self.avail_day_group_id, self.new_parent_id)

        # Um Inkonsistenzen zu vermeiden:
        old_parent_childs = db_services.AvailDayGroup.get_child_groups_from__parent_group(old_parent.id)
        if old_parent.nr_avail_day_groups and old_parent.nr_avail_day_groups > len(old_parent_childs):
            self.old_parent_nr_avail_day_groups = old_parent.nr_avail_day_groups
            db_services.AvailDayGroup.update_nr_avail_day_groups(old_parent.id, None)
        self.old_parent_id = old_parent.id


    def undo(self):
        db_services.AvailDayGroup.set_new_parent(self.avail_day_group_id, self.old_parent_id)
        if self.old_parent_nr_avail_day_groups:
            db_services.AvailDayGroup.update_nr_avail_day_groups(self.old_parent_id, self.old_parent_nr_avail_day_groups)

    def redo(self):
        old_parent = db_services.AvailDayGroup.get(self.avail_day_group_id).avail_day_group

        db_services.AvailDayGroup.set_new_parent(self.avail_day_group_id, self.new_parent_id)

        old_parent_childs = db_services.AvailDayGroup.get_child_groups_from__parent_group(old_parent.id)
        if old_parent.nr_avail_day_groups and old_parent.nr_avail_day_groups > len(old_parent_childs):
            self.old_parent_nr_avail_day_groups = old_parent.nr_avail_day_groups
            db_services.AvailDayGroup.update_nr_avail_day_groups(old_parent.id, None)



