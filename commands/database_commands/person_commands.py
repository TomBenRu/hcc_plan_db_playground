"""Command-Klassen für Person (Akteur / Mitarbeiter).

Standard-Update + Notes-Patch + Admin-Wechsel pro Projekt sowie
Präferenz-/Skill-/Flag-Verwaltung pro Person. Anlage, Löschung und
Team-Zuordnungen (Single/Multi/End) laufen seit 2026-05-16 ausschließlich
über `/admin/teams` im Web-UI — die zugehörigen Commands (`Create`,
`Delete`, `AssignToTeam`, `AddToTeam`, `RemoveFromTeam`) wurden entfernt.
Die `Create`-Klasse bleibt nur erhalten, weil Integration-Smoke-Skripte
sie nutzen — kein neuer GUI-Pfad ruft sie auf.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import person as api_person


class Create(Command):
    def __init__(self, person: schemas.PersonCreate, project_id: UUID):
        super().__init__()
        self.person = person
        self.project_id = project_id
        self.created_person: schemas.PersonShow | None = None

    def execute(self):
        self.created_person = api_person.create(self.person, self.project_id)

    def _undo(self):
        if self.created_person:
            api_person.delete(self.created_person.id)

    def _redo(self):
        if self.created_person:
            api_person.undelete(self.created_person.id)



class Update(Command):
    def __init__(self, person: schemas.PersonShow):
        super().__init__()
        self.new_data = person.model_copy()
        self.old_data = db_services.Person.get(person.id)
        self.updated_person: schemas.Person | None = None

    def execute(self):
        self.updated_person = api_person.update(self.new_data)

    def _undo(self):
        api_person.update(self.old_data)

    def _redo(self):
        api_person.update(self.new_data)


class UpdateNotes(Command):
    """Aktualisiert nur das notes-Feld einer Person.

    Schlanker Spezialfall von Update — vermeidet, dass das Widget die
    komplette PersonShow-Struktur (mit allen Collections) laden und
    zurueckschicken muss. Server liefert 204 No Content.

    notes_old wird optional vom Aufrufer uebergeben (spart bei remote DB
    einen Fetch der PersonShow-Hierarchie).
    """

    def __init__(self, person_id: UUID, notes: str, notes_old: str | None = None):
        super().__init__()
        self.person_id = person_id
        self.notes = notes
        if notes_old is None:
            notes_old = db_services.Person.get(person_id).notes
        self.notes_old = notes_old or ''

    def execute(self):
        api_person.update_notes(self.person_id, self.notes)

    def _undo(self):
        api_person.update_notes(self.person_id, self.notes_old)

    def _redo(self):
        api_person.update_notes(self.person_id, self.notes)


class UpdateAdminOfProject(Command):
    """Macht Person zum Admin des Projekts.

    old_admin_id wird optional vom Aufrufer uebergeben (vermeidet einen
    Project-Fetch bei remote DB). War vorher keiner, wird _had_old_admin
    auf False gesetzt und Undo entfernt die Admin-Zuordnung komplett.
    """

    _SENTINEL = object()

    def __init__(self, person_id: UUID, project_id: UUID, old_admin_id=_SENTINEL):
        super().__init__()
        self.person_id = person_id
        self.project_id = project_id
        if old_admin_id is UpdateAdminOfProject._SENTINEL:
            project = db_services.Project.get(project_id)
            old_admin_id = project.admin.id if project.admin else None
        self.old_admin_id: UUID | None = old_admin_id

    def execute(self):
        api_person.update_admin_of_project(self.person_id, self.project_id)

    def _undo(self):
        if self.old_admin_id is not None:
            api_person.update_admin_of_project(self.old_admin_id, self.project_id)
        else:
            api_person.clear_admin_of_project(self.person_id)

    def _redo(self):
        api_person.update_admin_of_project(self.person_id, self.project_id)


class PutInTimeOfDay(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_person.put_in_time_of_day(self.person_id, self.time_of_day_id)

    def _undo(self):
        api_person.remove_in_time_of_day(self.person_id, self.time_of_day_id)

    def _redo(self):
        api_person.put_in_time_of_day(self.person_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_person.remove_in_time_of_day(self.person_id, self.time_of_day_id)

    def _undo(self):
        api_person.put_in_time_of_day(self.person_id, self.time_of_day_id)

    def _redo(self):
        api_person.remove_in_time_of_day(self.person_id, self.time_of_day_id)


class NewTimeOfDayStandard(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = api_person.new_time_of_day_standard(self.person_id, self.time_of_day_id)

    def _undo(self):
        api_person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            api_person.new_time_of_day_standard(self.person_id, self.old_t_o_d_standard_id)

    def _redo(self):
        api_person.new_time_of_day_standard(self.person_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)

    def _undo(self):
        api_person.new_time_of_day_standard(self.person_id, self.time_of_day_id)

    def _redo(self):
        api_person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)


class PutInCombLocPossible(Command):
    def __init__(self, person_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        api_person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def _undo(self):
        api_person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def _redo(self):
        api_person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, person_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        api_person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def _undo(self):
        api_person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def _redo(self):
        api_person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)


class ReplaceCombLocPossibles(Command):
    """Ersetzt alle CombLocPossibles einer Person in einer Session.

    Undo: restore(old_comb_ids) — stellt den alten Zustand wieder her.
    Redo: restore(new_comb_ids) — reaktiviert die beim Execute erstellten CLPs.
    """

    def __init__(self, person_id: UUID,
                 original_ids: set[UUID],
                 pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]],
                 current_combs: list[schemas.CombinationLocationsPossible]):
        super().__init__()
        self.person_id = person_id
        self.original_ids = original_ids
        self.pending_creates = pending_creates
        self.current_combs = current_combs
        self._result: dict[str, list[UUID]] | None = None

    def execute(self):
        self._result = api_person.replace_comb_loc_possibles(
            self.person_id, self.original_ids, self.pending_creates, self.current_combs)

    def _undo(self):
        api_person.restore_comb_loc_possibles(
            self.person_id, self._result['old_comb_ids'])

    def _redo(self):
        api_person.restore_comb_loc_possibles(
            self.person_id, self._result['new_comb_ids'])


class PutInActorLocationPref(Command):
    def __init__(self, person_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        api_person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)

    def _undo(self):
        api_person.remove_location_pref(self.person_id, self.actor_loc_pref_id)

    def _redo(self):
        api_person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)


class RemoveActorLocationPref(Command):
    def __init__(self, person_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        api_person.remove_location_pref(self.person_id, self.actor_loc_pref_id)

    def _undo(self):
        api_person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)

    def _redo(self):
        api_person.remove_location_pref(self.person_id, self.actor_loc_pref_id)


class UpdateLocationPrefsBulk(Command):
    """Ersetzt alle Location-Präferenzen einer Person in einer Session.

    Analog zu ActorPlanPeriod.UpdateLocationPrefsBulk, aber für die Person-Default-
    Verknüpfung. Wiederverwendungslogik identisch.
    """
    def __init__(self, person_id: UUID, project_id: UUID, location_id_to_score: dict[UUID, float]):
        super().__init__()
        self.person_id = person_id
        self.project_id = project_id
        self.location_id_to_score = location_id_to_score
        self._result: dict[str, list[UUID]] | None = None

    def execute(self):
        self._result = api_person.update_location_prefs_bulk(
            self.person_id, self.project_id, self.location_id_to_score
        )

    def _undo(self):
        api_person.restore_location_prefs_bulk(
            self.person_id, self._result['old_pref_ids']
        )

    def _redo(self):
        self._result = api_person.update_location_prefs_bulk(
            self.person_id, self.project_id, self.location_id_to_score
        )


class PutInActorPartnerLocationPref(Command):
    def __init__(self, person_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        api_person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def _undo(self):
        api_person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def _redo(self):
        api_person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)


class RemoveActorPartnerLocationPref(Command):
    def __init__(self, person_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        api_person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def _undo(self):
        api_person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def _redo(self):
        api_person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)


class PutInFlag(Command):
    def __init__(self, person_id: UUID, flag_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.flag_id = flag_id

    def execute(self):
        api_person.put_in_flag(self.person_id, self.flag_id)

    def _undo(self):
        api_person.remove_flag(self.person_id, self.flag_id)

    def _redo(self):
        api_person.put_in_flag(self.person_id, self.flag_id)


class RemoveFlag(Command):
    def __init__(self, person_id: UUID, flag_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.flag_id = flag_id

    def execute(self):
        api_person.remove_flag(self.person_id, self.flag_id)

    def _undo(self):
        api_person.put_in_flag(self.person_id, self.flag_id)

    def _redo(self):
        api_person.remove_flag(self.person_id, self.flag_id)

class AddSkill(Command):
    def __init__(self, person_id: UUID, skill_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.skill_id = skill_id
        self.updated_object: schemas.PersonShow | None = None

    def execute(self):
        self.updated_object = api_person.add_skill(self.person_id, self.skill_id)

    def _undo(self):
        if self.updated_object:
            self.updated_object = api_person.remove_skill(self.updated_object.id, self.skill_id)

    def _redo(self):
        if self.updated_object:
            self.updated_object = api_person.add_skill(self.updated_object.id, self.skill_id)

class RemoveSkill(Command):
    def __init__(self, person_id: UUID, skill_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.skill_id = skill_id
        self.updated_object: schemas.PersonShow | None = None

    def execute(self):
        self.updated_object = api_person.remove_skill(self.person_id, self.skill_id)

    def _undo(self):
        if self.updated_object:
            self.updated_object = api_person.add_skill(self.updated_object.id, self.skill_id)

    def _redo(self):
        if self.updated_object:
            self.updated_object = api_person.remove_skill(self.updated_object.id, self.skill_id)
