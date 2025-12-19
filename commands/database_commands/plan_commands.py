import json
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, plan_period_id: UUID, name: str):
        super().__init__()
        self.plan_period_id = plan_period_id
        self.name = name
        self.plan: schemas.PlanShow | None = None

    def execute(self):
        self.plan = db_services.Plan.create(self.plan_period_id, self.name)

    def _undo(self):
        db_services.Plan.delete(self.plan.id)

    def _redo(self):
        db_services.Plan.undelete(self.plan.id)


class Delete(Command):
    def __init__(self, plan_id: UUID):
        super().__init__()
        self.plan_id = plan_id

    def execute(self):
        db_services.Plan.delete(self.plan_id)

    def _undo(self):
        db_services.Plan.undelete(self.plan_id)

    def _redo(self):
        db_services.Plan.delete(self.plan_id)


class Undelete(Command):
    def __init__(self, plan_id: UUID):
        super().__init__()
        self.plan_id = plan_id

    def execute(self):
        db_services.Plan.undelete(self.plan_id)

    def _undo(self):
        db_services.Plan.delete(self.plan_id)

    def _redo(self):
        db_services.Plan.undelete(self.plan_id)


class DeletePrepDeleted(Command):
    def __init__(self, plan_id: UUID):
        super().__init__()
        self.plan_id = plan_id

    def execute(self):
        db_services.Plan.delete_prep_deleted(self.plan_id)

    def _undo(self):
        ...

    def _redo(self):
        ...


class UpdateName(Command):
    def __init__(self, plan_id, new_name: str):
        super().__init__()
        self.plan_id = plan_id
        self.new_name = new_name
        self.old_name = db_services.Plan.get(plan_id).name
        self.updatet_plan: schemas.PlanShow | None = None

    def execute(self):
        self.updatet_plan = db_services.Plan.update_name(self.plan_id, self.new_name)

    def _undo(self):
        db_services.Plan.update_name(self.plan_id, self.old_name)

    def _redo(self):
        db_services.Plan.update_name(self.plan_id, self.new_name)


class UpdateLocationColumns(Command):
    def __init__(self, plan_id: UUID, location_columns: dict[int, list[UUID]]):
        super().__init__()
        self.plan_id = plan_id
        self._location_columns = location_columns
        self.location_columns_old = db_services.Plan.get_location_columns(plan_id)

    @property
    def location_columns(self):
        return json.dumps({k: [str(u) for u in v] for k, v in self._location_columns.items()})

    def execute(self):
        db_services.Plan.update_location_columns(self.plan_id, self.location_columns)

    def _undo(self):
        db_services.Plan.update_location_columns(self.plan_id, self.location_columns_old)

    def _redo(self):
        db_services.Plan.update_location_columns(self.plan_id, self.location_columns)

    def __str__(self) -> str:
        num_locations = sum(len(locs) for locs in self._location_columns.values())
        return f"Spaltenlayout aktualisieren: {num_locations} Standort(e)"


class UpdateNotes(Command):
    def __init__(self, plan_id, notes: str):
        super().__init__()
        self.plan_id = plan_id
        self.plan = db_services.Plan.get(plan_id)
        self.updated_plan: schemas.PlanShow | None = None
        self.notes = notes

    def execute(self):
        self.updated_plan = db_services.Plan.update_notes(self.plan_id, self.notes)

    def _undo(self):
        db_services.Plan.update_notes(self.plan_id, self.plan.notes)

    def _redo(self):
        db_services.Plan.update_notes(self.plan_id, self.notes)


class NewExcelExportSettings(Command):
    def __init__(self, plan_id: UUID, excel_settings: schemas.ExcelExportSettingsCreate):
        super().__init__()
        self.plan_id = plan_id
        self.plan = db_services.Plan.get(plan_id)
        self.excel_settings = excel_settings
        self.old_excel_settings_id = self.plan.excel_export_settings.id
        self.created_excel_settings: schemas.ExcelExportSettingsShow | None = None

    def execute(self):
        self.created_excel_settings = db_services.ExcelExportSettings.create(self.excel_settings)
        db_services.Plan.put_in_excel_settings(self.plan_id, self.created_excel_settings.id)

    def _undo(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.old_excel_settings_id)

    def _redo(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.created_excel_settings.id)


class PutInExcelExportSettings(Command):
    def __init__(self, plan_id: UUID, excel_settings_id: UUID):
        super().__init__()
        self.plan_id = plan_id
        self.old_excel_settings_id = db_services.Plan.get(plan_id).excel_export_settings.id
        self.excel_settings_id = excel_settings_id

    def execute(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.excel_settings_id)

    def _undo(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.old_excel_settings_id)

    def _redo(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.excel_settings_id)
