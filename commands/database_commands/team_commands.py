"""Command-Klassen für Team.

Enthält Commands für teamweite Konfigurationen:
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
