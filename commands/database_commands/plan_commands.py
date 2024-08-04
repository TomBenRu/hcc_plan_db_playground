import json
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, plan_period_id: UUID, name: str):
        self.plan_period_id = plan_period_id
        self.name = name
        self.plan: schemas.PlanShow | None = None

    def execute(self):
        self.plan = db_services.Plan.create(self.plan_period_id, self.name)

    def undo(self):
        db_services.Plan.delete(self.plan.id)

    def redo(self):
        db_services.Plan.undelete(self.plan.id)


class Delete(Command):
    def __init__(self, plan_id: UUID):
        self.plan_id = plan_id

    def execute(self):
        db_services.Plan.delete(self.plan_id)

    def undo(self):
        db_services.Plan.undelete(self.plan_id)

    def redo(self):
        db_services.Plan.delete(self.plan_id)


class DeletePrepDeleted(Command):
    def __init__(self, plan_id: UUID):
        self.plan_id = plan_id

    def execute(self):
        db_services.Plan.delete_prep_deleted(self.plan_id)

    def undo(self):
        ...

    def redo(self):
        ...


class UpdateName(Command):
    def __init__(self, plan_id, new_name: str):
        self.plan_id = plan_id
        self.new_name = new_name
        self.old_name = db_services.Plan.get(plan_id).name
        self.updatet_plan: schemas.PlanShow | None = None

    def execute(self):
        self.updatet_plan = db_services.Plan.update_name(self.plan_id, self.new_name)

    def undo(self):
        db_services.Plan.update_name(self.plan_id, self.old_name)

    def redo(self):
        db_services.Plan.update_name(self.plan_id, self.new_name)


class UpdateLocationColumns(Command):
    def __init__(self, plan_id: UUID, location_columns: dict[int, list[UUID]]):
        self.plan_id = plan_id
        self._location_columns = location_columns
        self._location_columns_old = db_services.Plan.get(plan_id).location_columns

    @property
    def location_columns(self):
        return json.dumps({k: [str(u) for u in v] for k, v in self._location_columns.items()})

    @property
    def location_columns_old(self):
        return json.dumps({k: [str(u) for u in v] for k, v in self._location_columns_old.items()})

    def execute(self):
        db_services.Plan.update_location_columns(self.plan_id, self.location_columns)

    def undo(self):
        db_services.Plan.update_location_columns(self.plan_id, self.location_columns_old)

    def redo(self):
        db_services.Plan.update_location_columns(self.plan_id, self.location_columns)


class NewExcelExportSettings(Command):
    def __init__(self, plan_id: UUID, excel_settings: schemas.ExcelExportSettingsCreate):
        self.plan_id = plan_id
        self.plan = db_services.Plan.get(plan_id)
        self.excel_settings = excel_settings
        self.old_excel_settings_id = self.plan.excel_export_settings.id
        self.created_excel_settings: schemas.ExcelExportSettingsShow | None = None

    def execute(self):
        self.created_excel_settings = db_services.ExcelExportSettings.create(self.excel_settings)
        db_services.Plan.put_in_excel_settings(self.plan_id, self.created_excel_settings.id)

    def undo(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.old_excel_settings_id)

    def redo(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.created_excel_settings.id)


class PutInExcelExportSettings(Command):
    def __init__(self, plan_id: UUID, excel_settings_id: UUID):
        self.plan_id = plan_id
        self.old_excel_settings_id = db_services.Plan.get(plan_id).excel_export_settings.id
        self.excel_settings_id = excel_settings_id

    def execute(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.excel_settings_id)

    def undo(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.old_excel_settings_id)

    def redo(self):
        db_services.Plan.put_in_excel_settings(self.plan_id, self.excel_settings_id)

