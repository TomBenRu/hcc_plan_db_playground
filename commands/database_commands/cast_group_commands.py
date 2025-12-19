from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, plan_period_id: UUID):
        super().__init__()
        self.plan_period_id = plan_period_id
        self.created_cast_group: schemas.CastGroupShow | None = None

    def execute(self):
        self.created_cast_group = db_services.CastGroup.create(plan_period_id=self.plan_period_id)

    def _undo(self):
        db_services.CastGroup.delete(self.created_cast_group.id)

    def _redo(self):
        self.created_cast_group = db_services.CastGroup.create(self.plan_period_id)


class Delete(Command):
    def __init__(self, cast_group_id: UUID):
        super().__init__()
        self.cast_group_id = cast_group_id
        self.cast_group = db_services.CastGroup.get(cast_group_id)

    def execute(self):
        db_services.CastGroup.delete(self.cast_group_id)

    def _undo(self):
        db_services.CastGroup.create(plan_period_id=self.cast_group.plan_period.id,
                                     restore_cast_group=self.cast_group)

    def _redo(self):
        db_services.CastGroup.delete(self.cast_group_id)


class SetNewParent(Command):
    def __init__(self, cast_group_id: UUID, new_parent_id: UUID):
        """new_parent_id ist die id der parent-cast_group."""
        super().__init__()
        self.cast_group_id = cast_group_id
        self.new_parent_id = new_parent_id

    def execute(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.new_parent_id)

    def _undo(self):
        db_services.CastGroup.remove_from_parent(self.cast_group_id, self.new_parent_id)

    def _redo(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.new_parent_id)


class RemoveFromParent(Command):
    def __init__(self, cast_group_id: UUID, parent_group_id: UUID):
        super().__init__()
        self.cast_group_id = cast_group_id
        self.parent_group_id = parent_group_id

    def execute(self):
        db_services.CastGroup.remove_from_parent(self.cast_group_id, self.parent_group_id)

    def _undo(self):
        db_services.CastGroup.set_new_parent(self.cast_group_id, self.parent_group_id)

    def _redo(self):
        db_services.CastGroup.remove_from_parent(self.cast_group_id, self.parent_group_id)


class UpdateFixedCast(Command):
    def __init__(self, cast_group_id: UUID, fixed_cast: str, fixed_cast_only_if_available: bool):
        super().__init__()
        self.cast_group_id = cast_group_id
        self.fixed_cast = fixed_cast
        self.fixed_cast_only_if_available = fixed_cast_only_if_available
        self.fixed_cast_old: str | None = None
        self.fixed_cast_only_if_available_old: bool = False

    def execute(self):
        cast_group = db_services.CastGroup.get(self.cast_group_id)
        self.fixed_cast_old = cast_group.fixed_cast
        self.fixed_cast_only_if_available_old = cast_group.fixed_cast_only_if_available
        db_services.CastGroup.update_fixed_cast(self.cast_group_id, self.fixed_cast,
                                                self.fixed_cast_only_if_available)

    def _undo(self):
        db_services.CastGroup.update_fixed_cast(self.cast_group_id, self.fixed_cast_old,
                                                self.fixed_cast_only_if_available_old)

    def _redo(self):
        db_services.CastGroup.update_fixed_cast(self.cast_group_id, self.fixed_cast,
                                                self.fixed_cast_only_if_available)


class UpdateNrActors(Command):
    def __init__(self, cast_group_id: UUID, nr_actors: int):
        super().__init__()
        self.cast_group_id = cast_group_id
        self.nr_actors = nr_actors
        self.nr_actors_old = db_services.CastGroup.get(cast_group_id).nr_actors

    def execute(self):
        db_services.CastGroup.update_nr_actors(self.cast_group_id, self.nr_actors)

    def _undo(self):
        db_services.CastGroup.update_nr_actors(self.cast_group_id, self.nr_actors_old)

    def _redo(self):
        db_services.CastGroup.update_nr_actors(self.cast_group_id, self.nr_actors)


class UpdateStrictCastPref(Command):
    def __init__(self, cast_group_id: UUID, strict_cast_pref: int):
        super().__init__()
        self.cast_group_id = cast_group_id
        self.strict_cast_pref = strict_cast_pref
        self.strict_cast_pref_old = db_services.CastGroup.get(cast_group_id).strict_cast_pref

    def execute(self):
        db_services.CastGroup.update_strict_cast_pref(self.cast_group_id, self.strict_cast_pref)

    def _undo(self):
        db_services.CastGroup.update_strict_cast_pref(self.cast_group_id, self.strict_cast_pref_old)

    def _redo(self):
        db_services.CastGroup.update_strict_cast_pref(self.cast_group_id, self.strict_cast_pref)


class UpdatePreferFixedCastEvents(Command):
    def __init__(self, cast_group_id: UUID, prefer_fixed_cast_events: bool):
        super().__init__()
        self.cast_group_id = cast_group_id
        self.prefer_fixed_cast_events = prefer_fixed_cast_events
        self.prefer_fixed_cast_events_old = db_services.CastGroup.get(cast_group_id).prefer_fixed_cast_events
        self.result: schemas.CastGroupShow | None = None

    def execute(self):
        self.result = db_services.CastGroup.update_prefer_fixed_cast_events(
            self.cast_group_id, self.prefer_fixed_cast_events
        )

    def _undo(self):
        self.result = db_services.CastGroup.update_prefer_fixed_cast_events(
            self.cast_group_id, self.prefer_fixed_cast_events_old
        )

    def _redo(self):
        self.result = db_services.CastGroup.update_prefer_fixed_cast_events(
            self.cast_group_id, self.prefer_fixed_cast_events
        )


class UpdateCustomRule(Command):
    def __init__(self, cast_group_id: UUID, custom_rule: str | None):
        super().__init__()
        self.cast_group_id = cast_group_id
        self.custom_rule = custom_rule
        self.custom_rule_old = db_services.CastGroup.get(cast_group_id).custom_rule

    def execute(self):
        db_services.CastGroup.update_custom_rule(self.cast_group_id, self.custom_rule)

    def _undo(self):
        db_services.CastGroup.update_custom_rule(self.cast_group_id, self.custom_rule_old)

    def _redo(self):
        db_services.CastGroup.update_custom_rule(self.cast_group_id, self.custom_rule)


class UpdateCastRule(Command):
    def __init__(self, cast_group_id: UUID, cast_rule_id: UUID | None):
        super().__init__()
        self.cast_group_id = cast_group_id
        self.cast_group = db_services.CastGroup.get(cast_group_id)
        self.cast_rule_id = cast_rule_id
        self.cast_rule_id_old = self.cast_group.cast_rule.id if self.cast_group.cast_rule else None

    def execute(self):
        db_services.CastGroup.update_cast_rule(self.cast_group_id, self.cast_rule_id)

    def _undo(self):
        db_services.CastGroup.update_cast_rule(self.cast_group_id, self.cast_rule_id_old)

    def _redo(self):
        db_services.CastGroup.update_cast_rule(self.cast_group_id, self.cast_rule_id)



