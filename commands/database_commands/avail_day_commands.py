"""Command-Klassen für AvailDay (Verfügbarkeitstag).

Das umfangreichste Command-Modul — kapselt alle Änderungen an AvailDays:
Erstellen (legt implizit auch eine AvailDayGroup an), Löschen, Tageszeit-Wechsel
sowie sämtliche Verwaltungsoperationen für Standortpräferenzen, Partner-Präferenzen,
Standortkombinationen und Skills.

Bulk-Reset-Commands (z. B. `ResetAllAvailDaysActorLocationPrefsToDefaults`) lesen
vorab IDs im Konstruktor, um das Undo effizient ohne Pydantic-Overhead durchzuführen.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import avail_day as api_avail_day


class Create(Command):
    def __init__(self, avail_day: schemas.AvailDayCreate):
        super().__init__()
        self.avail_day = avail_day.model_copy()
        self.created_avail_day: schemas.AvailDayShow | None = None

    def execute(self):
        self.created_avail_day = api_avail_day.create(
            date=self.avail_day.date,
            actor_plan_period_id=self.avail_day.actor_plan_period.id,
            time_of_day_id=self.avail_day.time_of_day.id,
        )

    def _undo(self):
        api_avail_day.delete(self.created_avail_day.id)

    def _redo(self):
        self.created_avail_day = api_avail_day.create(
            date=self.avail_day.date,
            actor_plan_period_id=self.avail_day.actor_plan_period.id,
            time_of_day_id=self.avail_day.time_of_day.id,
        )


class Delete(Command):
    def __init__(self, avail_day_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.avail_day_to_delete = db_services.AvailDay.get(avail_day_id)

    def execute(self):
        api_avail_day.delete(self.avail_day_id)

    def _undo(self):
        """todo: Schwierigkeit: Beim Löschen wurden unter Umständen kaskadenweise AvailDayGroups gelöscht.
           diese können auf diese Weise nicht wiederhergestellt werden."""
        self.avail_day_id = api_avail_day.create(
            date=self.avail_day_to_delete.date,
            actor_plan_period_id=self.avail_day_to_delete.actor_plan_period.id,
            time_of_day_id=self.avail_day_to_delete.time_of_day.id,
        ).id

    def _redo(self):
        api_avail_day.delete(self.avail_day_id)


class UpdateTimeOfDays(Command):
    def __init__(self, avail_day_id: UUID, time_of_days: list[schemas.TimeOfDay]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.new_time_of_days = time_of_days
        self.old_time_of_days = db_services.AvailDay.get(avail_day_id).time_of_days

    def execute(self):
        api_avail_day.update_time_of_days(self.avail_day_id, self.new_time_of_days)

    def _undo(self):
        api_avail_day.update_time_of_days(self.avail_day_id, self.old_time_of_days)

    def _redo(self):
        api_avail_day.update_time_of_days(self.avail_day_id, self.new_time_of_days)


class UpdateTimeOfDay(Command):
    def __init__(self, avail_day: schemas.AvailDayShow, new_time_of_day_id: UUID):
        super().__init__()
        self.avail_day = avail_day
        self.old_time_of_day_id = self.avail_day.time_of_day.id
        self.new_time_of_day_id = new_time_of_day_id

    def execute(self):
        api_avail_day.update_time_of_day(self.avail_day.id, self.new_time_of_day_id)

    def _undo(self):
        api_avail_day.update_time_of_day(self.avail_day.id, self.old_time_of_day_id)

    def _redo(self):
        api_avail_day.update_time_of_day(self.avail_day.id, self.new_time_of_day_id)


class PutInCombLocPossible(Command):
    def __init__(self, avail_day_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        api_avail_day.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def _undo(self):
        api_avail_day.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def _redo(self):
        api_avail_day.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)


class PutInCombLocPossibles(Command):
    def __init__(self, avail_day_id: UUID, comb_loc_poss_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.comb_loc_poss_ids = comb_loc_poss_ids

    def execute(self):
        api_avail_day.put_in_comb_loc_possibles(self.avail_day_id, self.comb_loc_poss_ids)

    def _undo(self):
        for comb_loc_poss_id in self.comb_loc_poss_ids:
            api_avail_day.remove_comb_loc_possible(self.avail_day_id, comb_loc_poss_id)

    def _redo(self):
        api_avail_day.put_in_comb_loc_possibles(self.avail_day_id, self.comb_loc_poss_ids)


class RemoveCombLocPossible(Command):
    def __init__(self, avail_day_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        api_avail_day.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def _undo(self):
        api_avail_day.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def _redo(self):
        api_avail_day.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)


class ClearCombLocPossibles(Command):
    def __init__(self, avail_day_id: UUID, existing_comb_loc_poss_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.existing_comb_loc_poss_ids = existing_comb_loc_poss_ids

    def execute(self):
        api_avail_day.clear_comb_loc_possibles(self.avail_day_id)

    def _undo(self):
        api_avail_day.put_in_comb_loc_possibles(self.avail_day_id, self.existing_comb_loc_poss_ids)

    def _redo(self):
        api_avail_day.clear_comb_loc_possibles(self.avail_day_id)


class PutInActorLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        api_avail_day.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def _undo(self):
        api_avail_day.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def _redo(self):
        api_avail_day.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)


class PutInActorLocationPrefs(Command):
    def __init__(self, avail_day_id: UUID, actor_loc_pref_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_loc_pref_ids = actor_loc_pref_ids

    def execute(self):
        api_avail_day.put_in_location_prefs(self.avail_day_id, self.actor_loc_pref_ids)

    def _undo(self):
        for actor_loc_pref_id in self.actor_loc_pref_ids:
            api_avail_day.remove_location_pref(self.avail_day_id, actor_loc_pref_id)

    def _redo(self):
        api_avail_day.put_in_location_prefs(self.avail_day_id, self.actor_loc_pref_ids)


class RemoveActorLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        api_avail_day.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def _undo(self):
        api_avail_day.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def _redo(self):
        api_avail_day.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)


class ClearActorLocationPrefs(Command):
    def __init__(self, avail_day_id: UUID, existing_actor_loc_pref_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.existing_actor_loc_pref_ids = existing_actor_loc_pref_ids

    def execute(self):
        api_avail_day.clear_location_prefs(self.avail_day_id)

    def _undo(self):
        api_avail_day.put_in_location_prefs(self.avail_day_id, self.existing_actor_loc_pref_ids)

    def _redo(self):
        api_avail_day.clear_location_prefs(self.avail_day_id)


class PutInActorPartnerLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        api_avail_day.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def _undo(self):
        api_avail_day.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def _redo(self):
        api_avail_day.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)


class PutInActorPartnerLocationPrefs(Command):
    def __init__(self, avail_day_id: UUID, actor_partner_loc_pref_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_partner_loc_pref_ids = actor_partner_loc_pref_ids

    def execute(self):
        api_avail_day.put_in_partner_location_prefs(self.avail_day_id, self.actor_partner_loc_pref_ids)

    def _undo(self):
        for actor_partner_loc_pref_id in self.actor_partner_loc_pref_ids:
            api_avail_day.remove_partner_location_pref(self.avail_day_id, actor_partner_loc_pref_id)

    def _redo(self):
        api_avail_day.put_in_partner_location_prefs(self.avail_day_id, self.actor_partner_loc_pref_ids)


class RemoveActorPartnerLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        api_avail_day.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def _undo(self):
        api_avail_day.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def _redo(self):
        api_avail_day.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)


class ClearActorPartnerLocationPrefs(Command):
    def __init__(self, avail_day_id: UUID, existing_actor_partner_loc_pref_ids: list[UUID] | None = None):
        super().__init__()
        self.avail_day_id = avail_day_id
        if existing_actor_partner_loc_pref_ids is None:
            self.existing_actor_partner_loc_pref_ids = db_services.ActorPartnerLocationPref.get_all_from__avail_day(
                self.avail_day_id)
        else:
            self.existing_actor_partner_loc_pref_ids = existing_actor_partner_loc_pref_ids

    def execute(self):
        api_avail_day.clear_partner_location_prefs(self.avail_day_id)

    def _undo(self):
        api_avail_day.put_in_partner_location_prefs(self.avail_day_id, self.existing_actor_partner_loc_pref_ids)

    def _redo(self):
        api_avail_day.clear_partner_location_prefs(self.avail_day_id)


class ReplacePartnerPrefsForAvailDays(Command):
    """Ersetzt alle Partner-Prefs für alle AvailDays an einem Tag in einer Session.

    Analog zu ReplaceAvailDayLocationPrefs, aber für Partner-Präferenzen.
    Undo: stellt pro AvailDay den alten Zustand wieder her.
    Redo: führt den Replace erneut aus.
    """

    def __init__(self, avail_day_ids: list[UUID], person_id: UUID,
                 new_prefs: list[tuple[UUID, UUID, float]]):
        super().__init__()
        self.avail_day_ids = avail_day_ids
        self.person_id = person_id
        self.new_prefs = new_prefs
        self._created_ids: list[UUID] = []
        self._old_pref_ids_per_avail_day: dict[UUID, list[UUID]] = {}

    def execute(self):
        self._created_ids, self._old_pref_ids_per_avail_day = (
            db_services.ActorPartnerLocationPref.replace_all_for_avail_days(
                self.avail_day_ids, self.person_id, self.new_prefs))

    def _undo(self):
        db_services.ActorPartnerLocationPref.undo_replace_all_for_avail_days(
            self.avail_day_ids, self._created_ids, self._old_pref_ids_per_avail_day)

    def _redo(self):
        self._created_ids, self._old_pref_ids_per_avail_day = (
            db_services.ActorPartnerLocationPref.replace_all_for_avail_days(
                self.avail_day_ids, self.person_id, self.new_prefs))


class ResetAllAvailDaysActorPartnerLocationPrefsToDefaults(Command):
    def __init__(self, actor_plan_period_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        self.existing_actor_partner_loc_pref_ids_per_avail_day: dict[UUID, list[UUID]] = (
            db_services.ActorPartnerLocationPref.get_ids_per_avail_day_of_actor_plan_period(self.actor_plan_period_id)
        )

    def execute(self):
        api_avail_day.reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults(
            self.actor_plan_period_id)

    def _undo(self):
        for avail_day_id, actor_partner_loc_pref_ids in self.existing_actor_partner_loc_pref_ids_per_avail_day.items():
            api_avail_day.clear_partner_location_prefs(avail_day_id)
            api_avail_day.put_in_partner_location_prefs(avail_day_id, actor_partner_loc_pref_ids)

    def _redo(self):
        api_avail_day.reset_all_avail_days_partner_location_prefs_of_actor_plan_period_to_defaults(
            self.actor_plan_period_id)


class ResetAllAvailDaysActorLocationPrefsToDefaults(Command):
    """Setzt Location-Prefs aller AvailDays einer ActorPlanPeriod auf Defaults zurück."""

    def __init__(self, actor_plan_period_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        # Leichtgewichtige ID-Abfrage für Undo-Daten (keine Pydantic-Serialisierung!)
        self.existing_actor_loc_pref_ids_per_avail_day: dict[UUID, list[UUID]] = (
            db_services.ActorLocationPref.get_loc_pref_ids_per_avail_day_of_actor_plan_period(
                self.actor_plan_period_id)
        )

    def execute(self):
        api_avail_day.reset_all_avail_days_location_prefs_of_actor_plan_period_to_defaults(
            self.actor_plan_period_id)

    def _undo(self):
        for avail_day_id, actor_loc_pref_ids in self.existing_actor_loc_pref_ids_per_avail_day.items():
            api_avail_day.clear_location_prefs(avail_day_id)
            api_avail_day.put_in_location_prefs(avail_day_id, actor_loc_pref_ids)

    def _redo(self):
        api_avail_day.reset_all_avail_days_location_prefs_of_actor_plan_period_to_defaults(
            self.actor_plan_period_id)


class ReplaceAvailDayCombLocPossibles(Command):
    """Ersetzt CombLocPossibles für alle AvailDays an einem Tag in einer Session.

    avail_day_ids[0] ist der primäre AvailDay (aus dem Dialog), alle anderen werden synchronisiert.
    Undo: restore(old_comb_ids_per_avail_day) — stellt pro AvailDay den alten Zustand wieder her.
    Redo: restore({avd_id: new_comb_ids}) — setzt alle AvailDays auf den neuen Zustand.
    """

    def __init__(self, avail_day_ids: list[UUID], person_id: UUID,
                 original_ids: set[UUID],
                 pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]],
                 current_combs: list[schemas.CombinationLocationsPossible]):
        super().__init__()
        self.avail_day_ids = avail_day_ids
        self.person_id = person_id
        self.original_ids = original_ids
        self.pending_creates = pending_creates
        self.current_combs = current_combs
        self._result: dict | None = None

    def execute(self):
        self._result = api_avail_day.replace_comb_loc_possibles_for_avail_days(
            self.avail_day_ids, self.person_id,
            self.original_ids, self.pending_creates, self.current_combs)

    def _undo(self):
        api_avail_day.restore_comb_loc_possibles_for_avail_days(
            self._result['old_comb_ids_per_avail_day'])

    def _redo(self):
        redo_target = {avd_id: self._result['new_comb_ids'] for avd_id in self.avail_day_ids}
        api_avail_day.restore_comb_loc_possibles_for_avail_days(redo_target)


class ReplaceAvailDayLocationPrefs(Command):
    """Ersetzt Location-Prefs für alle AvailDays an einem Tag in einer Session.

    Analog zu ReplaceAvailDayCombLocPossibles.
    Undo: restore(old_pref_ids_per_avail_day) — stellt pro AvailDay den alten Zustand wieder her.
    Redo: restore({avd_id: new_pref_ids}) — setzt alle AvailDays auf den neuen Zustand.
    """

    def __init__(self, avail_day_ids: list[UUID], person_id: UUID, project_id: UUID,
                 location_id_to_score: dict[UUID, float]):
        super().__init__()
        self.avail_day_ids = avail_day_ids
        self.person_id = person_id
        self.project_id = project_id
        self.location_id_to_score = location_id_to_score
        self._result: dict | None = None

    def execute(self):
        self._result = api_avail_day.replace_location_prefs_for_avail_days(
            self.avail_day_ids, self.person_id, self.project_id, self.location_id_to_score)

    def _undo(self):
        api_avail_day.restore_location_prefs_for_avail_days(
            self._result['old_pref_ids_per_avail_day'])

    def _redo(self):
        redo_target = {avd_id: self._result['new_pref_ids'] for avd_id in self.avail_day_ids}
        api_avail_day.restore_location_prefs_for_avail_days(redo_target)


class ResetAllAvailDaysCombLocPossiblesToDefaults(Command):
    """Setzt CombLocPossibles aller AvailDays einer ActorPlanPeriod auf Defaults zurück."""

    def __init__(self, actor_plan_period_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        # Leichtgewichtige ID-Abfrage für Undo-Daten (keine Pydantic-Serialisierung!)
        self.existing_comb_loc_poss_ids_per_avail_day: dict[UUID, list[UUID]] = (
            db_services.CombinationLocationsPossible.get_comb_loc_poss_ids_per_avail_day_of_actor_plan_period(
                self.actor_plan_period_id)
        )

    def execute(self):
        api_avail_day.reset_all_avail_days_comb_loc_possibles_of_actor_plan_period_to_defaults(
            self.actor_plan_period_id)

    def _undo(self):
        for avail_day_id, comb_loc_poss_ids in self.existing_comb_loc_poss_ids_per_avail_day.items():
            api_avail_day.clear_comb_loc_possibles(avail_day_id)
            api_avail_day.put_in_comb_loc_possibles(avail_day_id, comb_loc_poss_ids)

    def _redo(self):
        api_avail_day.reset_all_avail_days_comb_loc_possibles_of_actor_plan_period_to_defaults(
            self.actor_plan_period_id)


class AddSkill(Command):
    def __init__(self, avail_day_id: UUID, skill_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.skill_id = skill_id
        self.updated_object: schemas.PersonShow | None = None

    def execute(self):
        self.updated_object = api_avail_day.add_skill(self.avail_day_id, self.skill_id)

    def _undo(self):
        if self.updated_object:
            api_avail_day.remove_skill(self.updated_object.id, self.skill_id)

    def _redo(self):
        if self.updated_object:
            api_avail_day.add_skill(self.updated_object.id, self.skill_id)

class RemoveSkill(Command):
    def __init__(self, avail_day_id: UUID, skill_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.skill_id = skill_id
        self.updated_object: schemas.AvailDayShow | None = None

    def execute(self):
        self.updated_object = api_avail_day.remove_skill(self.avail_day_id, self.skill_id)

    def _undo(self):
        if self.updated_object:
            api_avail_day.add_skill(self.updated_object.id, self.skill_id)

    def _redo(self):
        if self.updated_object:
            api_avail_day.remove_skill(self.updated_object.id, self.skill_id)


class RemoveAllSkillsFromAllAvailDays(Command):
    """Entfernt alle Skills von allen AvailDays einer ActorPlanPeriod."""

    def __init__(self, actor_plan_period_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        # Leichtgewichtige ID-Abfrage für Undo-Daten (keine Pydantic-Serialisierung!)
        self.existing_skill_ids_per_avail_day: dict[UUID, list[UUID]] = (
            db_services.AvailDay.get_skill_ids_per_avail_day_of_actor_plan_period(
                self.actor_plan_period_id)
        )

    def execute(self):
        api_avail_day.clear_all_skills_of_actor_plan_period(self.actor_plan_period_id)

    def _undo(self):
        for avail_day_id, skill_ids in self.existing_skill_ids_per_avail_day.items():
            api_avail_day.put_in_skills(avail_day_id, skill_ids)

    def _redo(self):
        api_avail_day.clear_all_skills_of_actor_plan_period(self.actor_plan_period_id)


class ResetAllSkillsOfAllAvailDaysToPersonDefaults(Command):
    """Setzt Skills aller AvailDays einer ActorPlanPeriod auf Person-Defaults zurück."""

    def __init__(self, actor_plan_period_id: UUID):
        super().__init__()
        self.actor_plan_period_id = actor_plan_period_id
        # Leichtgewichtige ID-Abfrage für Undo-Daten (keine Pydantic-Serialisierung!)
        self.existing_skill_ids_per_avail_day: dict[UUID, list[UUID]] = (
            db_services.AvailDay.get_skill_ids_per_avail_day_of_actor_plan_period(
                self.actor_plan_period_id)
        )

    def execute(self):
        api_avail_day.reset_all_skills_of_actor_plan_period_to_person_defaults(
            self.actor_plan_period_id)

    def _undo(self):
        for avail_day_id, skill_ids in self.existing_skill_ids_per_avail_day.items():
            api_avail_day.clear_skills(avail_day_id)
            api_avail_day.put_in_skills(avail_day_id, skill_ids)

    def _redo(self):
        api_avail_day.reset_all_skills_of_actor_plan_period_to_person_defaults(
            self.actor_plan_period_id)
