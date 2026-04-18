"""Command-Klassen für AvailDayGroup (Verfügbarkeitstag-Gruppe / Baum).

Verwaltet die Baumstruktur der AvailDayGroups unterhalb einer ActorPlanPeriod.
Besonderheit beim `Delete`- und `SetNewParent`-Command: Wird durch die Änderung
der Kinderzahl die `nr_avail_day_groups` des Elternknotens inkonsistent, wird sie
automatisch auf `None` gesetzt und beim Undo wiederhergestellt.
`Create` akzeptiert entweder eine `actor_plan_period_id` (Master) oder eine
`avail_day_group_id` (Kind-Knoten) — nie beides gleichzeitig.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import avail_day_group as api_avail_day_group


class Create(Command):
    """Die seltsame Benennung der Parameter ist der gemeinsamen DlgGroupMode-Klasse geschuldet."""
    def __init__(self, *, loc_act_plan_period_id: UUID = None, event_avail_day_group_id: UUID = None):
        """Die Parameter 'loc_act_plan_period_id' und 'event_avail_day_group_id' können nicht beide None sein."""
        super().__init__()
        if not loc_act_plan_period_id and not event_avail_day_group_id:
            raise AttributeError('Die Parameter "actor_plan_period_id" und "avail_day_group_id" '
                                 'können nicht beide None sein.')
        self.actor_plan_period_id = loc_act_plan_period_id
        self.avail_day_group_id = event_avail_day_group_id

        self.created_group: schemas.AvailDayGroupShow | None = None

    def execute(self):
        self.created_group = api_avail_day_group.create(actor_plan_period_id=self.actor_plan_period_id,
                                                              avail_day_group_id=self.avail_day_group_id)

    def _undo(self):
        api_avail_day_group.delete(self.created_group.id)

    def _redo(self):
        self.created_group = api_avail_day_group.create(
            actor_plan_period_id=self.actor_plan_period_id,
            avail_day_group_id=self.avail_day_group_id,
            undo_id=self.created_group.id if self.created_group else None,
        )


class Delete(Command):
    def __init__(self, avail_day_group_id: UUID):
        super().__init__()
        self.avail_day_group_id = avail_day_group_id
        self.avail_day_group = db_services.AvailDayGroup.get(avail_day_group_id)
        self.parent_avail_day_group_id: UUID | None = None
        self.parent_nr_avail_day_groups: int | None = None

    def execute(self):
        api_avail_day_group.delete(self.avail_day_group_id)

        # Um Inkonsistenzen zu vermeiden:
        parent_avd_groups = db_services.AvailDayGroup.get_child_groups_from__parent_group(self.avail_day_group.avail_day_group.id)
        parent_nr_avail_day_groups = self.avail_day_group.avail_day_group.nr_avail_day_groups
        if parent_nr_avail_day_groups and parent_nr_avail_day_groups  > len(parent_avd_groups):
            self.parent_nr_avail_day_groups = parent_nr_avail_day_groups
            api_avail_day_group.update_nr_avail_day_groups(self.avail_day_group.avail_day_group.id, None)

    def _undo(self):
        actor_plan_period_id = (self.avail_day_group.actor_plan_period.id
                                if self.avail_day_group.actor_plan_period else None)
        avail_day_group_id = self.avail_day_group.avail_day_group.id if self.avail_day_group.avail_day_group else None
        api_avail_day_group.create(
            actor_plan_period_id=actor_plan_period_id,
            avail_day_group_id=avail_day_group_id,
            undo_id=self.avail_day_group_id
        )
        if self.parent_nr_avail_day_groups:
            api_avail_day_group.update_nr_avail_day_groups(self.avail_day_group.avail_day_group.id,
                                                                 self.parent_nr_avail_day_groups)

    def _redo(self):
        api_avail_day_group.delete(self.avail_day_group_id)

        parent_avd_groups = db_services.AvailDayGroup.get_child_groups_from__parent_group(
            self.avail_day_group.avail_day_group.id)
        parent_nr_avail_day_groups = self.avail_day_group.avail_day_group.nr_avail_day_groups
        if parent_nr_avail_day_groups and parent_nr_avail_day_groups > len(parent_avd_groups):
            self.parent_nr_avail_day_groups = parent_nr_avail_day_groups
            api_avail_day_group.update_nr_avail_day_groups(self.avail_day_group.avail_day_group.id, None)


class UpdateNrAvailDayGroups(Command):
    def __init__(self, avail_day_group_id: UUID, nr_avail_day_groups: int | None):
        super().__init__()
        self.avail_day_group_id= avail_day_group_id
        self.nr_avail_day_groups = nr_avail_day_groups
        self.nr_avail_day_groups_old: int | None = None

    def execute(self):
        avail_day_group = db_services.AvailDayGroup.get(self.avail_day_group_id)
        self.nr_avail_day_groups_old = avail_day_group.nr_avail_day_groups
        api_avail_day_group.update_nr_avail_day_groups(self.avail_day_group_id, self.nr_avail_day_groups)

    def _undo(self):
        api_avail_day_group.update_nr_avail_day_groups(self.avail_day_group_id, self.nr_avail_day_groups_old)

    def _redo(self):
        api_avail_day_group.update_nr_avail_day_groups(self.avail_day_group_id, self.nr_avail_day_groups)


class UpdateVariationWeight(Command):
    def __init__(self, avail_day_group_id: UUID, variation_weight: int):
        super().__init__()
        self.avail_day_group_id= avail_day_group_id
        self.variation_weight = variation_weight
        self.variation_weight_old: int | None = None

    def execute(self):
        avail_day_group = db_services.AvailDayGroup.get(self.avail_day_group_id)
        self.variation_weight_old = avail_day_group.variation_weight
        api_avail_day_group.update_variation_weight(self.avail_day_group_id, self.variation_weight)

    def _undo(self):
        api_avail_day_group.update_variation_weight(self.avail_day_group_id, self.variation_weight_old)

    def _redo(self):
        api_avail_day_group.update_variation_weight(self.avail_day_group_id, self.variation_weight)


class UpdateMandatoryNrAvailDayGroups(Command):
    def __init__(self, avail_day_group_id: UUID, mandatory_nr_avail_day_groups: int | None):
        super().__init__()
        self.avail_day_group_id = avail_day_group_id
        self.mandatory_nr_avail_day_groups = mandatory_nr_avail_day_groups
        self.mandatory_nr_avail_day_groups_old = db_services.AvailDayGroup.get(avail_day_group_id).mandatory_nr_avail_day_groups

    def execute(self):
        api_avail_day_group.update_mandatory_nr_avail_day_groups(
            self.avail_day_group_id, self.mandatory_nr_avail_day_groups)

    def _undo(self):
        api_avail_day_group.update_mandatory_nr_avail_day_groups(
            self.avail_day_group_id, self.mandatory_nr_avail_day_groups_old)

    def _redo(self):
        api_avail_day_group.update_mandatory_nr_avail_day_groups(
            self.avail_day_group_id, self.mandatory_nr_avail_day_groups)


class SetNewParent(Command):
    def __init__(self, avail_day_group_id: UUID, new_parent_id: UUID):
        """new_parent_id ist die id der parent-avail_day_group."""
        super().__init__()
        self.avail_day_group_id = avail_day_group_id
        self.new_parent_id = new_parent_id
        self.old_parent_id: UUID | None = None
        self.old_parent_nr_avail_day_groups: int | None = None

    def execute(self):
        old_parent_id, old_parent_nr_adg = db_services.AvailDayGroup.get_parent_info(self.avail_day_group_id)

        api_avail_day_group.set_new_parent(self.avail_day_group_id, self.new_parent_id)

        # Um Inkonsistenzen zu vermeiden (COUNT nach dem Move — Kind ist bereits weg):
        if old_parent_id and old_parent_nr_adg:
            remaining = db_services.AvailDayGroup.count_children(old_parent_id)
            if old_parent_nr_adg > remaining:
                self.old_parent_nr_avail_day_groups = old_parent_nr_adg
                api_avail_day_group.update_nr_avail_day_groups(old_parent_id, None)
        self.old_parent_id = old_parent_id

    def _undo(self):
        api_avail_day_group.set_new_parent(self.avail_day_group_id, self.old_parent_id)
        if self.old_parent_nr_avail_day_groups:
            api_avail_day_group.update_nr_avail_day_groups(self.old_parent_id, self.old_parent_nr_avail_day_groups)

    def _redo(self):
        old_parent_id, old_parent_nr_adg = db_services.AvailDayGroup.get_parent_info(self.avail_day_group_id)

        api_avail_day_group.set_new_parent(self.avail_day_group_id, self.new_parent_id)

        if old_parent_id and old_parent_nr_adg:
            remaining = db_services.AvailDayGroup.count_children(old_parent_id)
            if old_parent_nr_adg > remaining:
                self.old_parent_nr_avail_day_groups = old_parent_nr_adg
                api_avail_day_group.update_nr_avail_day_groups(old_parent_id, None)


class SetNewParentBatch(Command):
    """Verschiebt N AvailDayGroups auf einmal in einer einzigen DB-Session.

    Ersetzt N einzelne SetNewParent-Commands in move_selected_items_to_group.
    """

    def __init__(self, moves: list[tuple[UUID, UUID]]):
        super().__init__()
        self.moves = moves
        self.old_parent_infos: list[tuple[UUID | None, int | None]] = []
        self.nr_resets: dict[UUID, int] = {}

    def execute(self):
        self.old_parent_infos, self.nr_resets = api_avail_day_group.set_new_parent_batch(self.moves)

    def _undo(self):
        for (child_id, _), (old_parent_id, _) in zip(self.moves, self.old_parent_infos):
            if old_parent_id:
                api_avail_day_group.set_new_parent(child_id, old_parent_id)
        for old_parent_id, old_nr in self.nr_resets.items():
            api_avail_day_group.update_nr_avail_day_groups(old_parent_id, old_nr)

    def _redo(self):
        self.old_parent_infos, self.nr_resets = api_avail_day_group.set_new_parent_batch(self.moves)



