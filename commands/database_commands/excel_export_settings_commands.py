"""Command-Klassen für ExcelExportSettings (Excel-Export-Einstellungen).

`Update` ersetzt alle Felder eines ExcelExportSettings-Eintrags. Undo hält den
alten Zustand vor Command-Ausfuehrung (via db_services.get) und stellt ihn
wieder her.
"""
from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import excel_export_settings as api_excel_export_settings


class Update(Command):
    def __init__(self, new_settings: schemas.ExcelExportSettings):
        super().__init__()
        self.new_settings = new_settings.model_copy()
        old = db_services.ExcelExportSettings.get(new_settings.id)
        self.old_settings = schemas.ExcelExportSettings.model_validate(
            old.model_dump())

    def execute(self):
        api_excel_export_settings.update(self.new_settings)

    def _undo(self):
        api_excel_export_settings.update(self.old_settings)

    def _redo(self):
        api_excel_export_settings.update(self.new_settings)