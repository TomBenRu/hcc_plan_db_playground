"""Command-Klassen für Team.

Enthält Commands für teamweite Konfigurationen:
- `Create` / `Update` / `Delete`: Team-CRUD. Delete ist soft (prep_delete),
  Undo via undelete.
- `PutInCombLocPossible` / `RemoveCombLocPossible`: Standortkombinationen.
- `NewExcelExportSettings`: Erstellt neue Einstellungen und verknüpft sie;
  Undo schaltet auf die vorherigen Einstellungen zurück.
- `PutInExcelExportSettings`: Verknüpft bestehende Einstellungen.
- `UpdateNotes`: Ändert Team-Notizen.
"""
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import team as api_team, excel_export_settings as api_excel_export_settings


class Create(Command):
    """Team-Erstellung. Undo soft-loescht, Redo undelete (selbe ID)."""

    def __init__(self, name: str, project_id: UUID, dispatcher_id: UUID | None = None):
        super().__init__()
        self.name = name
        self.project_id = project_id
        self.dispatcher_id = dispatcher_id
        self.created_team: schemas.TeamShow | None = None

    def execute(self):
        self.created_team = api_team.create(self.name, self.project_id, self.dispatcher_id)

    def _undo(self):
        if self.created_team:
            api_team.delete(self.created_team.id)

    def _redo(self):
        if self.created_team:
            api_team.undelete(self.created_team.id)


class Update(Command):
    """Aktualisiert Name + Dispatcher (schemas.Team)."""

    def __init__(self, team: schemas.Team):
        super().__init__()
        self.new_data = team.model_copy()
        old = db_services.Team.get(team.id)
        self.old_data = schemas.Team.model_validate(old.model_dump())

    def execute(self):
        api_team.update(self.new_data)

    def _undo(self):
        api_team.update(self.old_data)

    def _redo(self):
        api_team.update(self.new_data)


class Delete(Command):
    """Soft-Delete mit Undo via undelete."""

    def __init__(self, team_id: UUID):
        super().__init__()
        self.team_id = team_id

    def execute(self):
        api_team.delete(self.team_id)

    def _undo(self):
        api_team.undelete(self.team_id)

    def _redo(self):
        api_team.delete(self.team_id)


class PutInCombLocPossible(Command):
    def __init__(self, team_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.team_id = team_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        api_team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def _undo(self):
        api_team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def _redo(self):
        api_team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, team_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.team_id = team_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        api_team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def _undo(self):
        api_team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def _redo(self):
        api_team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)


class ReplaceCombLocPossibles(Command):
    """Ersetzt alle CombLocPossibles eines Teams in einer Session.

    Undo: restore(old_comb_ids) — stellt den alten Zustand wieder her.
    Redo: restore(new_comb_ids) — reaktiviert die beim Execute erstellten CLPs.
    """

    def __init__(self, team_id: UUID,
                 original_ids: set[UUID],
                 pending_creates: list[tuple[UUID, schemas.CombinationLocationsPossibleCreate]],
                 current_combs: list[schemas.CombinationLocationsPossible]):
        super().__init__()
        self.team_id = team_id
        self.original_ids = original_ids
        self.pending_creates = pending_creates
        self.current_combs = current_combs
        self._result: dict[str, list[UUID]] | None = None

    def execute(self):
        self._result = api_team.replace_comb_loc_possibles(
            self.team_id, self.original_ids, self.pending_creates, self.current_combs)

    def _undo(self):
        api_team.restore_comb_loc_possibles(
            self.team_id, self._result['old_comb_ids'])

    def _redo(self):
        api_team.restore_comb_loc_possibles(
            self.team_id, self._result['new_comb_ids'])


class NewExcelExportSettings(Command):
    def __init__(self, team_id: UUID, excel_settings: schemas.ExcelExportSettingsCreate):
        super().__init__()
        self.team_id = team_id
        self.team = db_services.Team.get(team_id)
        self.excel_settings = excel_settings
        self.old_excel_settings_id = self.team.excel_export_settings.id
        self.created_excel_settings: schemas.ExcelExportSettingsShow | None = None

    def execute(self):
        self.created_excel_settings = api_excel_export_settings.create(self.excel_settings)
        api_team.put_in_excel_settings(self.team_id, self.created_excel_settings.id)

    def _undo(self):
        api_team.put_in_excel_settings(self.team_id, self.old_excel_settings_id)

    def _redo(self):
        api_team.put_in_excel_settings(self.team_id, self.created_excel_settings.id)


class PutInExcelExportSettings(Command):
    def __init__(self, team_id: UUID, excel_settings_id: UUID):
        super().__init__()
        self.team_id = team_id
        self.old_excel_settings_id = db_services.Team.get(team_id).excel_export_settings.id
        self.excel_settings_id = excel_settings_id

    def execute(self):
        api_team.put_in_excel_settings(self.team_id, self.excel_settings_id)

    def _undo(self):
        api_team.put_in_excel_settings(self.team_id, self.old_excel_settings_id)

    def _redo(self):
        api_team.put_in_excel_settings(self.team_id, self.excel_settings_id)


class UpdateNotes(Command):
    def __init__(self, team_id: UUID, notes: str):
        super().__init__()
        self.team_id = team_id
        self.notes = notes
        self.team = db_services.Team.get(team_id)
        self.updated_team: schemas.TeamShow | None = None

    def execute(self):
        self.updated_team = api_team.update_notes(self.team_id, self.notes)

    def _undo(self):
        api_team.update_notes(self.team_id, self.team.notes)

    def _redo(self):
        api_team.update_notes(self.team_id, self.notes)
