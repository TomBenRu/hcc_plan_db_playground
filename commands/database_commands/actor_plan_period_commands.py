"""Command-Klassen für ActorPlanPeriod (Akteur-Planperiode).

Verwaltet sämtliche Änderungen an der Verknüpfung zwischen Person und PlanPeriod,
darunter Tageszeiten, Tageszeit-Standards, Standortpräferenzen, Partner-Präferenzen,
Standortkombinationen, gewünschte Einsätze und Notizen.

Redo bei `Create` übergibt die original ID, um referenzielle Integrität zu wahren.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import actor_plan_period as api_app


class ReplaceCombLocPossibles(Command):
    """Ersetzt alle CombLocPossibles eines ActorPlanPeriods in einer einzigen Session.

    Wiederverwendungslogik: Existiert in der Person bereits eine CombLocPossible mit
    gleichem locations_of_work-ID-Set und time_span_between, wird sie übernommen
    statt neu angelegt. Verwaiste CLPs werden soft-deleted.

    Undo: restore(old_comb_ids)
    Redo: restore(new_comb_ids) — reaktiviert die beim Execute erstellten CLPs statt neue zu erzeugen.
    """
    def __init__(self, actor_plan_period_id: UUID, person_id: UUID,
                 original_ids: set[UUID],
                 pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]],
                 current_combs: list[schemas.CombinationLocationsPossible]):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.person_id = person_id
        self.original_ids = original_ids
        self.pending_creates = pending_creates
        self.current_combs = current_combs
        self._result: dict[str, list[UUID]] | None = None

    def execute(self):
        self._result = db_services.ActorPlanPeriod.replace_comb_loc_possibles(
            self.actor_plan_period_id, self.person_id,
            self.original_ids, self.pending_creates, self.current_combs,
        )

    def _undo(self):
        db_services.ActorPlanPeriod.restore_comb_loc_possibles(
            self.actor_plan_period_id, self._result['old_comb_ids']
        )

    def _redo(self):
        db_services.ActorPlanPeriod.restore_comb_loc_possibles(
            self.actor_plan_period_id, self._result['new_comb_ids']
        )


class Create(Command):
    def __init__(self, plan_period_id: UUID, person_id: UUID):
        super().__init__()
        self.plan_period_id = plan_period_id
        self.person_id = person_id
        self.created_actor_plan_period: schemas.ActorPlanPeriodShow | None = None

    def execute(self):
        self.created_actor_plan_period = api_app.create(self.plan_period_id, self.person_id)

    def _undo(self):
        api_app.delete(self.created_actor_plan_period.id)

    def _redo(self):
        api_app.create(self.plan_period_id, self.person_id, self.created_actor_plan_period.id)


class Update(Command):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        super().__init__()
        self.new_data = actor_plan_period.model_copy()
        self.old_data = db_services.ActorPlanPeriod.get(actor_plan_period.id)

    def execute(self):
        api_app.update(self.new_data)

    def _undo(self):
        api_app.update(self.old_data)

    def _redo(self):
        api_app.update(self.new_data)


class PutInTimeOfDay(Command):
    def __init__(self, actor_plan_period_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.ActorPlanPeriod.put_in_time_of_day(self.actor_plan_period_id, self.time_of_day_id)

    def _undo(self):
        db_services.ActorPlanPeriod.remove_in_time_of_day(self.actor_plan_period_id, self.time_of_day_id)

    def _redo(self):
        db_services.ActorPlanPeriod.put_in_time_of_day(self.actor_plan_period_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, actor_plan_period_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_in_time_of_day(self.actor_plan_period_id, self.time_of_day_id)

    def _undo(self):
        db_services.ActorPlanPeriod.put_in_time_of_day(self.actor_plan_period_id, self.time_of_day_id)

    def _redo(self):
        db_services.ActorPlanPeriod.remove_in_time_of_day(self.actor_plan_period_id, self.time_of_day_id)


class NewTimeOfDayStandard(Command):
    def __init__(self, actor_plan_period_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = db_services.ActorPlanPeriod.new_time_of_day_standard(self.actor_plan_period_id,
                                                                                             self.time_of_day_id)

    def _undo(self):
        db_services.ActorPlanPeriod.remove_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            db_services.ActorPlanPeriod.new_time_of_day_standard(self.actor_plan_period_id, self.old_t_o_d_standard_id)

    def _redo(self):
        db_services.ActorPlanPeriod.new_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, actor_plan_period_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)

    def _undo(self):
        db_services.ActorPlanPeriod.new_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)

    def _redo(self):
        db_services.ActorPlanPeriod.remove_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)


class PutInCombLocPossible(Command):
    def __init__(self, actor_plan_period_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.ActorPlanPeriod.put_in_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)

    def _undo(self):
        db_services.ActorPlanPeriod.remove_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)

    def _redo(self):
        db_services.ActorPlanPeriod.put_in_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, actor_plan_period_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)

    def _undo(self):
        db_services.ActorPlanPeriod.put_in_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)

    def _redo(self):
        db_services.ActorPlanPeriod.remove_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)


class PutInActorLocationPref(Command):
    def __init__(self, actor_plan_period_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.ActorPlanPeriod.put_in_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)

    def _undo(self):
        db_services.ActorPlanPeriod.remove_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)

    def _redo(self):
        db_services.ActorPlanPeriod.put_in_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)


class RemoveActorLocationPref(Command):
    def __init__(self, actor_plan_period_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)

    def _undo(self):
        db_services.ActorPlanPeriod.put_in_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)

    def _redo(self):
        db_services.ActorPlanPeriod.remove_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)


class UpdateLocationPrefsBulk(Command):
    """Ersetzt alle Location-Präferenzen einer ActorPlanPeriod in einer Session.

    Wiederverwendungslogik: Existiert eine Person-Pref mit gleicher Location und
    gleichem Score, wird sie verknüpft statt neu angelegt.
    Undo/Redo stellen den jeweiligen Zustand vollständig wieder her.
    """
    def __init__(self, actor_plan_period_id: UUID, location_id_to_score: dict[UUID, float]):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.location_id_to_score = location_id_to_score
        self._result: dict[str, list[UUID]] | None = None

    def execute(self):
        self._result = db_services.ActorPlanPeriod.update_location_prefs_bulk(
            self.actor_plan_period_id, self.location_id_to_score
        )

    def _undo(self):
        db_services.ActorPlanPeriod.restore_location_prefs_bulk(
            self.actor_plan_period_id, self._result['old_pref_ids']
        )

    def _redo(self):
        self._result = db_services.ActorPlanPeriod.update_location_prefs_bulk(
            self.actor_plan_period_id, self.location_id_to_score
        )


class PutInActorPartnerLocationPref(Command):
    def __init__(self, actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.ActorPlanPeriod.put_in_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)

    def _undo(self):
        db_services.ActorPlanPeriod.remove_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)

    def _redo(self):
        db_services.ActorPlanPeriod.put_in_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)


class RemoveActorPartnerLocationPref(Command):
    def __init__(self, actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)

    def _undo(self):
        db_services.ActorPlanPeriod.put_in_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)

    def _redo(self):
        db_services.ActorPlanPeriod.remove_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)


class UpdateRequestedAssignments(Command):
    def __init__(self, actor_plan_period_id: UUID, requested_assignments: int, required_assignments: bool):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.requested_assignments = requested_assignments
        self.required_assignments = required_assignments
        self.actor_plan_period_old: schemas.ActorPlanPeriodShow = db_services.ActorPlanPeriod.get(actor_plan_period_id)
        self.requested_assignments_old = self.actor_plan_period_old.requested_assignments
        self.required_assignments_old = self.actor_plan_period_old.required_assignments

    def execute(self):
        api_app.update_requested_assignments(
            self.actor_plan_period_id, self.requested_assignments, self.required_assignments)

    def _undo(self):
        api_app.update_requested_assignments(
            self.actor_plan_period_id, self.requested_assignments_old, self.required_assignments_old)

    def _redo(self):
        api_app.update_requested_assignments(
            self.actor_plan_period_id, self.requested_assignments, self.required_assignments)


class UpdateNotes(Command):
    def __init__(self, actor_plan_period_id: UUID, notes: str):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.updated_actor_plan_period: schemas.ActorPlanPeriodShow | None = None
        self.notes = notes
        self.notes_old = db_services.ActorPlanPeriod.get(actor_plan_period_id).notes

    def execute(self):
        self.updated_actor_plan_period = api_app.update_notes(
            self.actor_plan_period_id, self.notes)

    def _undo(self):
        self.updated_actor_plan_period = api_app.update_notes(
            self.actor_plan_period_id, self.notes_old)

    def _redo(self):
        self.updated_actor_plan_period = api_app.update_notes(
            self.actor_plan_period_id, self.notes
        )
