"""Command-Klassen für LocationOfWork (Arbeitsort).

Standort-Anlage, Löschung und Team-Zuordnungen laufen seit 2026-05-16
ausschließlich über `/admin/teams` im Web-UI. Hier verbleiben die
Plan-Intelligenz-Commands plus `Update` für Stammdaten-Patches, die der
Desktop weiterhin braucht (z. B. `nr_actors`).

- Einfache Feldupdates: Tageszeiten, fixed_cast, SkillGroups, Notes
- `Update`: Stammdaten-Update mit Undo
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import location_of_work as api_low


class UpdateNotes(Command):
    """Aktualisiert die Notizen der LocationOfWork. Altes notes-Feld kann
    optional vom Aufrufer uebergeben werden (spart DB-Fetch bei remote DB).
    """

    def __init__(self, location_id: UUID, notes: str, notes_old: str | None = None):
        super().__init__()
        self.location_id = location_id
        self.notes = notes
        if notes_old is None:
            notes_old = db_services.LocationOfWork.get(location_id).notes
        self.notes_old = notes_old or ''

    def execute(self):
        api_low.update_notes(self.location_id, self.notes)

    def _undo(self):
        api_low.update_notes(self.location_id, self.notes_old)

    def _redo(self):
        api_low.update_notes(self.location_id, self.notes)


class Update(Command):
    def __init__(self, location_of_work: schemas.LocationOfWorkShow):
        super().__init__()
        self.new_data = location_of_work.model_copy()
        self.old_data = db_services.LocationOfWork.get(location_of_work.id)
        self.updated_location_of_work: schemas.LocationOfWorkShow | None = None

    def execute(self):
        self.updated_location_of_work = api_low.update(self.new_data)

    def _undo(self):
        api_low.update(self.old_data)

    def _redo(self):
        api_low.update(self.new_data)


class PutInTimeOfDay(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_low.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def _undo(self):
        api_low.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def _redo(self):
        api_low.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_low.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def _undo(self):
        api_low.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def _redo(self):
        api_low.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)


class NewTimeOfDayStandard(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = api_low.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def _undo(self):
        api_low.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            api_low.new_time_of_day_standard(self.location_of_work_id, self.old_t_o_d_standard_id)

    def _redo(self):
        api_low.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_low.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def _undo(self):
        api_low.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def _redo(self):
        api_low.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)


class UpdateFixedCast(Command):
    def __init__(self, location_of_work_id: UUID, fixed_cast: str | None, fixed_cast_only_if_available: bool):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.fixed_cast = fixed_cast
        self.fixed_cast_only_if_available = fixed_cast_only_if_available
        self.fixed_cast_old: str | None = None
        self.fixed_cast_only_if_available_old: bool = False

    def execute(self):
        location_of_work = db_services.LocationOfWork.get(self.location_of_work_id)
        self.fixed_cast_old = location_of_work.fixed_cast
        self.fixed_cast_only_if_available_old = location_of_work.fixed_cast_only_if_available
        api_low.update_fixed_cast(self.location_of_work_id, self.fixed_cast,
                                                    self.fixed_cast_only_if_available)

    def _undo(self):
        api_low.update_fixed_cast(self.location_of_work_id, self.fixed_cast_old,
                                                    self.fixed_cast_only_if_available_old)

    def _redo(self):
        api_low.update_fixed_cast(self.location_of_work_id, self.fixed_cast,
                                                    self.fixed_cast_only_if_available)


class AddSkillGroup(Command):
    def __init__(self, location_of_work_id: UUID, skill_group_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.skill_group_id = skill_group_id
        self.location_of_work: schemas.LocationOfWorkShow | None = None

    def execute(self):
        self.location_of_work = api_low.add_skill_group(
            self.location_of_work_id, self.skill_group_id)

    def _undo(self):
        if self.location_of_work:
            api_low.remove_skill_group(self.location_of_work_id, self.skill_group_id)

    def _redo(self):
        if self.location_of_work:
            api_low.add_skill_group(self.location_of_work_id, self.skill_group_id)


class RemoveSkillGroup(Command):
    def __init__(self, location_of_work_id: UUID, skill_group_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.skill_group_id = skill_group_id
        self.location_of_work: schemas.LocationOfWorkShow | None = None

    def execute(self):
        self.location_of_work = api_low.remove_skill_group(
            self.location_of_work_id, self.skill_group_id)

    def _undo(self):
        if self.location_of_work:
            api_low.add_skill_group(self.location_of_work_id, self.skill_group_id)

    def _redo(self):
        if self.location_of_work:
            api_low.remove_skill_group(self.location_of_work_id, self.skill_group_id)
