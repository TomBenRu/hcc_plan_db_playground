from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class PutInCombLocPossible(Command):
    def __init__(self, team_id: UUID, comb_loc_poss_id: UUID):

        self.team_id = team_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.Team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.Team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.Team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, team_id: UUID, comb_loc_poss_id: UUID):

        self.team_id = team_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.Team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.Team.put_in_comb_loc_possible(self.team_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.Team.remove_comb_loc_possible(self.team_id, self.comb_loc_poss_id)


class NewExcelExportSettings(Command):
    def __init__(self, team_id: UUID, excel_settings: schemas.ExcelExportSettingsCreate):
        self.team_id = team_id
        self.team = db_services.Team.get(team_id)
        self.excel_settings_id_of_project = self.team.excel_export_settings.id
        self.excel_settings = excel_settings
        self.old_excel_settings_id = self.team.excel_export_settings.id
        self.created_excel_settings: schemas.ExcelExportSettingsShow | None = None

    def execute(self):
        self.created_excel_settings = db_services.ExcelExportSettings.create(self.excel_settings)
        db_services.Team.put_in_excel_settings(self.team_id, self.created_excel_settings.id)
        if self.old_excel_settings_id != self.excel_settings_id_of_project:
            db_services.ExcelExportSettings.set_deleted(self.old_excel_settings_id)

    def undo(self):
        if self.old_excel_settings_id != self.excel_settings_id_of_project:
            db_services.ExcelExportSettings.set_undeleted(self.old_excel_settings_id)
        db_services.Team.put_in_excel_settings(self.team_id, self.old_excel_settings_id)
        db_services.ExcelExportSettings.set_deleted(self.created_excel_settings.id)

    def redo(self):
        db_services.ExcelExportSettings.set_undeleted(self.created_excel_settings.id)
        db_services.Team.put_in_excel_settings(self.team_id, self.created_excel_settings.id)
        if self.old_excel_settings_id != self.excel_settings_id_of_project:
            db_services.ExcelExportSettings.set_deleted(self.old_excel_settings_id)

