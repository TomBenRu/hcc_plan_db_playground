"""Command-Klassen für EventGroup (Veranstaltungsgruppen-Baum).

Analoges Pendant zu `avail_day_group_commands` für Events. Beim `Delete`- und
`SetNewParent`-Command wird `nr_event_groups` des Elternknotens bei Inkonsistenz
automatisch auf `None` gesetzt und beim Undo wiederhergestellt. `Create` nutzt
`undo_group_id`, um beim Redo exakt dieselbe UUID zu vergeben.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import event_group as api_event_group


class Create(Command):
    """Die seltsame Benennung der Parameter ist der gemeinsamen DlgGroupMode-Klasse geschuldet."""
    def __init__(self, *, loc_act_plan_period_id: UUID = None, event_avail_day_group_id: UUID = None):
        """Die Parameter 'loc_act_plan_period_id' und 'event_avail_day_group_id' können nicht beide None sein."""
        super().__init__()
        if not loc_act_plan_period_id and not event_avail_day_group_id:
            raise AttributeError('Die Parameter "actor_plan_period_id" und "avail_day_group_id" '
                                 'können nicht beide None sein.')
        self.location_plan_period_id = loc_act_plan_period_id
        self.event_group_id = event_avail_day_group_id

        self.created_group: schemas.EventGroupShow | None = None

    def execute(self):
        self.created_group = api_event_group.create(location_plan_period_id=self.location_plan_period_id,
                                                           event_group_id=self.event_group_id, undo_group_id=None)

    def _undo(self):
        api_event_group.delete(self.created_group.id)

    def _redo(self):
        self.created_group = api_event_group.create(location_plan_period_id=self.location_plan_period_id,
                                                           event_group_id=self.event_group_id,
                                                           undo_group_id=self.created_group.id)


class Delete(Command):
    def __init__(self, event_group_id: UUID):
        super().__init__()
        self.event_group_id = event_group_id
        self.event_group = db_services.EventGroup.get(event_group_id)
        self.parent_event_group_id: UUID | None = None
        self.parent_nr_event_groups: int | None = None

    def execute(self):
        api_event_group.delete(self.event_group_id)

        # Um Inkonsistenzen zu vermeiden:
        parent_event_groups = db_services.EventGroup.get_child_groups_from__parent_group(self.event_group.event_group.id)
        parent_nr_event_groups = self.event_group.event_group.nr_event_groups
        if parent_nr_event_groups and parent_nr_event_groups > len(parent_event_groups):
            self.parent_nr_event_groups = parent_nr_event_groups
            api_event_group.update_nr_event_groups(self.event_group.event_group.id, None)

    def _undo(self):
        location_plan_period_id = (self.event_group.location_plan_period.id
                                   if self.event_group.location_plan_period else None)
        parent_event_group_id = self.event_group.event_group.id if self.event_group.event_group else None
        api_event_group.create(location_plan_period_id=location_plan_period_id,
                                      event_group_id=parent_event_group_id,
                                      undo_group_id=self.event_group_id)
        if self.parent_nr_event_groups:
            api_event_group.update_nr_event_groups(self.event_group.event_group.id, self.parent_nr_event_groups)

    def _redo(self):
        api_event_group.delete(self.event_group_id)

        parent_event_groups = db_services.EventGroup.get_child_groups_from__parent_group(
            self.event_group.event_group.id)
        parent_nr_event_groups = self.event_group.event_group.nr_event_groups
        if parent_nr_event_groups and parent_nr_event_groups > len(parent_event_groups):
            self.parent_nr_event_groups = parent_nr_event_groups
            api_event_group.update_nr_event_groups(self.event_group.event_group.id, None)


class UpdateNrEventGroups(Command):
    def __init__(self, event_group_id: UUID, nr_event_groups: int | None):
        super().__init__()
        self.event_group_id = event_group_id
        self.nr_event_groups = nr_event_groups
        self.nr_event_groups_old: int | None = None

    def execute(self):
        event_group = db_services.EventGroup.get(self.event_group_id)
        self.nr_event_groups_old = event_group.nr_event_groups
        api_event_group.update_nr_event_groups(self.event_group_id, self.nr_event_groups)

    def _undo(self):
        api_event_group.update_nr_event_groups(self.event_group_id, self.nr_event_groups_old)

    def _redo(self):
        api_event_group.update_nr_event_groups(self.event_group_id, self.nr_event_groups)


class UpdateVariationWeight(Command):
    def __init__(self, event_group_id: UUID, variation_weight: int):
        super().__init__()
        self.event_group_id = event_group_id
        self.variation_weight = variation_weight
        self.variation_weight_old: int | None = None

    def execute(self):
        event_group = db_services.EventGroup.get(self.event_group_id)
        self.variation_weight_old = event_group.variation_weight
        api_event_group.update_variation_weight(self.event_group_id, self.variation_weight)

    def _undo(self):
        api_event_group.update_variation_weight(self.event_group_id, self.variation_weight_old)

    def _redo(self):
        api_event_group.update_variation_weight(self.event_group_id, self.variation_weight)


class SetNewParent(Command):
    def __init__(self, event_group_id: UUID, new_parent_id: UUID):
        """new_parent_id ist die id der parent-avail_day_group."""
        super().__init__()
        self.event_group_id = event_group_id
        self.new_parent_id = new_parent_id
        self.old_parent_id: UUID | None = None
        self.old_parent_nr_event_groups: int | None = None

    def execute(self):
        old_parent_id, old_parent_nr_eg = db_services.EventGroup.get_parent_info(self.event_group_id)

        api_event_group.set_new_parent(self.event_group_id, self.new_parent_id)

        # Um Inkonsistenzen zu vermeiden (COUNT nach dem Move — Kind ist bereits weg):
        if old_parent_id and old_parent_nr_eg:
            remaining = db_services.EventGroup.count_children(old_parent_id)
            if old_parent_nr_eg > remaining:
                self.old_parent_nr_event_groups = old_parent_nr_eg
                api_event_group.update_nr_event_groups(old_parent_id, None)
        self.old_parent_id = old_parent_id

    def _undo(self):
        api_event_group.set_new_parent(self.event_group_id, self.old_parent_id)
        if self.old_parent_nr_event_groups:
            api_event_group.update_nr_event_groups(self.old_parent_id, self.old_parent_nr_event_groups)

    def _redo(self):
        old_parent_id, old_parent_nr_eg = db_services.EventGroup.get_parent_info(self.event_group_id)

        api_event_group.set_new_parent(self.event_group_id, self.new_parent_id)

        if old_parent_id and old_parent_nr_eg:
            remaining = db_services.EventGroup.count_children(old_parent_id)
            if old_parent_nr_eg > remaining:
                self.old_parent_nr_event_groups = old_parent_nr_eg
                api_event_group.update_nr_event_groups(old_parent_id, None)


class SetNewParentBatch(Command):
    """Verschiebt N EventGroups auf einmal in einer einzigen DB-Session.

    Ersetzt N einzelne SetNewParent-Commands in move_selected_items_to_group.
    """

    def __init__(self, moves: list[tuple[UUID, UUID]]):
        super().__init__()
        self.moves = moves
        self.old_parent_infos: list[tuple[UUID | None, int | None]] = []
        self.nr_resets: dict[UUID, int] = {}

    def execute(self):
        self.old_parent_infos, self.nr_resets = api_event_group.set_new_parent_batch(self.moves)

    def _undo(self):
        for (child_id, _), (old_parent_id, _) in zip(self.moves, self.old_parent_infos):
            if old_parent_id:
                api_event_group.set_new_parent(child_id, old_parent_id)
        for old_parent_id, old_nr in self.nr_resets.items():
            api_event_group.update_nr_event_groups(old_parent_id, old_nr)

    def _redo(self):
        self.old_parent_infos, self.nr_resets = api_event_group.set_new_parent_batch(self.moves)
