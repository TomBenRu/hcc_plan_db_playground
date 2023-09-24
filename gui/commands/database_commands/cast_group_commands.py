from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, plan_period_id: UUID):
        self.plan_period_id = plan_period_id
        self.created_cast_group: schemas.CastGroupShow | None = None

    def execute(self):
        self.created_cast_group = db_services.CastGroup.create(plan_period_id=self.plan_period_id)

    def undo(self):
        db_services.CastGroup.delete(self.created_cast_group.id)

    def redo(self):
        self.created_cast_group = db_services.CastGroup.create(self.plan_period_id)


class Delete(Command):
    def __init__(self, cast_group_id: UUID):
        self.cast_group_id = cast_group_id
        self.cast_group = db_services.CastGroup.get(cast_group_id)

    def execute(self):
        db_services.CastGroup.delete(self.cast_group_id)

    def undo(self):
        db_services.CastGroup.create(plan_period_id=self.cast_group.plan_period.id,
                                     restore_cast_group=self.cast_group)

    def redo(self):
        db_services.CastGroup.delete(self.cast_group_id)


class SetNewParent(Command):
    def __init__(self, cast_group_id: UUID, new_parent_id: UUID):
        """new_parent_id ist die id der parent-cast_group."""
        self.cast_group_id = cast_group_id
        self.new_parent_id = new_parent_id

    def execute(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.new_parent_id)

    def undo(self):
        db_services.CastGroup.remove_from_parent(self.cast_group_id, self.new_parent_id)

    def redo(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.new_parent_id)


class RemoveFromParent(Command):
    def __init__(self, cast_group_id: UUID, parent_group_id: UUID):
        self.cast_group_id = cast_group_id
        self.parent_group_id = parent_group_id

    def execute(self):
        db_services.CastGroup.remove_from_parent(self.cast_group_id, self.parent_group_id)

    def undo(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.parent_group_id)

    def redo(self):
        db_services.CastGroup.remove_from_parent(self.cast_group_id, self.parent_group_id)



class UpdateFixedCast(Command):
    def __init__(self, cast_group_id: UUID, fixed_cast: str):
        self.cast_group_id = cast_group_id
        self.fixed_cast = fixed_cast
        self.fixed_cast_old = None

    def execute(self):
        self.fixed_cast_old = db_services.CastGroup.get(self.cast_group_id).fixed_cast
        db_services.CastGroup.update_fixed_cast(self.cast_group_id, self.fixed_cast)

    def undo(self):
        db_services.CastGroup.update_fixed_cast(self.cast_group_id, self.fixed_cast_old)

    def redo(self):
        db_services.CastGroup.update_fixed_cast(self.cast_group_id, self.fixed_cast)


class UpdateNrActors(Command):
    def __init__(self, cast_group_id: UUID, nr_actors: int):
        self.cast_group_id = cast_group_id
        self.nr_actors = nr_actors
        self.nr_actors_old = db_services.CastGroup.get(cast_group_id).nr_actors

    def execute(self):
        db_services.CastGroup.update_nr_actors(self.cast_group_id, self.nr_actors)

    def undo(self):
        db_services.CastGroup.update_nr_actors(self.cast_group_id, self.nr_actors_old)

    def redo(self):
        db_services.CastGroup.update_nr_actors(self.cast_group_id, self.nr_actors)


class UpdateStrictCastPref(Command):
    def __init__(self, cast_group_id: UUID, strict_cast_pref: int):
        self.cast_group_id = cast_group_id
        self.strict_cast_pref = strict_cast_pref
        self.strict_cast_pref_old = db_services.CastGroup.get(cast_group_id).strict_cast_pref

    def execute(self):
        db_services.CastGroup.update_strict_cast_pref(self.cast_group_id, self.strict_cast_pref)

    def undo(self):
        db_services.CastGroup.update_strict_cast_pref(self.cast_group_id, self.strict_cast_pref_old)

    def redo(self):
        db_services.CastGroup.update_strict_cast_pref(self.cast_group_id, self.strict_cast_pref)


class UpdateCustomRule(Command):
    def __init__(self, cast_group_id: UUID, custom_rule: str | None):
        self.cast_group_id = cast_group_id
        self.custom_rule = custom_rule
        self.custom_rule_old = db_services.CastGroup.get(cast_group_id).custom_rule

    def execute(self):
        db_services.CastGroup.update_custom_rule(self.cast_group_id, self.custom_rule)

    def undo(self):
        db_services.CastGroup.update_custom_rule(self.cast_group_id, self.custom_rule_old)

    def redo(self):
        db_services.CastGroup.update_custom_rule(self.cast_group_id, self.custom_rule)


class UpdateCastRule(Command):
    def __init__(self, cast_group_id: UUID, cast_rule_id: UUID | None):
        self.cast_group_id = cast_group_id
        self.cast_group = db_services.CastGroup.get(cast_group_id)
        self.cast_rule_id = cast_rule_id
        self.cast_rule_id_old = self.cast_group.cast_rule.id if self.cast_group.cast_rule else None

    def execute(self):
        db_services.CastGroup.update_cast_rule(self.cast_group_id, self.cast_rule_id)

    def undo(self):
        db_services.CastGroup.update_cast_rule(self.cast_group_id, self.cast_rule_id_old)

    def redo(self):
        db_services.CastGroup.update_cast_rule(self.cast_group_id, self.cast_rule_id)



