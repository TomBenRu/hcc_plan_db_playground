"""Command-Klassen für Plan (Dienstplan).

Verwaltet den Lebenszyklus eines Plans: Erstellen, Soft-Delete, Wiederherstellen
(`Undelete`) und endgültiges Löschen (`DeletePrepDeleted`, kein Undo möglich).
Außerdem: Namensänderung, Notizen, Spaltenlayout (JSON-serialisiert) und
Excel-Export-Einstellungen.

`UpdateLocationColumns` serialisiert das `dict[int, list[UUID]]` in JSON,
bevor es in der DB gespeichert wird.
"""
import json
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command
from gui.api_client import plan as api_plan, excel_export_settings as api_excel_export_settings


class Create(Command):
    def __init__(self, plan_period_id: UUID, name: str):
        super().__init__()
        self.plan_period_id = plan_period_id
        self.name = name
        self.plan: schemas.PlanShow | None = None

    def execute(self):
        self.plan = api_plan.create(self.plan_period_id, self.name)

    def _undo(self):
        api_plan.delete(self.plan.id)

    def _redo(self):
        api_plan.undelete(self.plan.id)


class Delete(Command):
    def __init__(self, plan_id: UUID):
        super().__init__()
        self.plan_id = plan_id

    def execute(self):
        api_plan.delete(self.plan_id)

    def _undo(self):
        api_plan.undelete(self.plan_id)

    def _redo(self):
        api_plan.delete(self.plan_id)


class Undelete(Command):
    def __init__(self, plan_id: UUID):
        super().__init__()
        self.plan_id = plan_id

    def execute(self):
        api_plan.undelete(self.plan_id)

    def _undo(self):
        api_plan.delete(self.plan_id)

    def _redo(self):
        api_plan.undelete(self.plan_id)


class DeletePrepDeleted(Command):
    def __init__(self, plan_id: UUID):
        super().__init__()
        self.plan_id = plan_id

    def execute(self):
        api_plan.delete_prep_deleted(self.plan_id)

    def _undo(self):
        ...

    def _redo(self):
        ...


class DeletePrepDeletesFromTeam(Command):
    """Hartes Löschen aller prep-deleted Plaene eines Teams. Irreversibel —
    Undo/Redo sind no-ops, weil hard-deletes nicht wiederhergestellt werden
    können. Aufrufer holt Bestaetigungs-Dialog ein.
    """

    def __init__(self, team_id: UUID):
        super().__init__()
        self.team_id = team_id

    def execute(self):
        api_plan.delete_prep_deletes_from__team(self.team_id)

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
        self.updatet_plan = api_plan.update_name(self.plan_id, self.new_name)

    def _undo(self):
        api_plan.update_name(self.plan_id, self.old_name)

    def _redo(self):
        api_plan.update_name(self.plan_id, self.new_name)


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
        api_plan.update_location_columns(self.plan_id, self.location_columns)

    def _undo(self):
        api_plan.update_location_columns(self.plan_id, self.location_columns_old)

    def _redo(self):
        api_plan.update_location_columns(self.plan_id, self.location_columns)

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
        self.updated_plan = api_plan.update_notes(self.plan_id, self.notes)

    def _undo(self):
        api_plan.update_notes(self.plan_id, self.plan.notes)

    def _redo(self):
        api_plan.update_notes(self.plan_id, self.notes)


class SetBinding(Command):
    """Markiert einen Plan als verbindlich; hebt bei anderen Plänen der gleichen
    Planperiode is_binding auf."""

    def __init__(self, plan_id: UUID):
        super().__init__()
        self.plan_id = plan_id
        self.previous_binding_plan_id: UUID | None = None

    def execute(self):
        self.previous_binding_plan_id = api_plan.set_is_binding(self.plan_id, True)

    def _undo(self):
        api_plan.set_is_binding(self.plan_id, False)
        if self.previous_binding_plan_id:
            api_plan.set_is_binding(self.previous_binding_plan_id, True)

    def _redo(self):
        api_plan.set_is_binding(self.plan_id, True)


class NewExcelExportSettings(Command):
    def __init__(self, plan_id: UUID, excel_settings: schemas.ExcelExportSettingsCreate):
        super().__init__()
        self.plan_id = plan_id
        self.plan = db_services.Plan.get(plan_id)
        self.excel_settings = excel_settings
        self.old_excel_settings_id = self.plan.excel_export_settings.id
        self.created_excel_settings: schemas.ExcelExportSettingsShow | None = None

    def execute(self):
        self.created_excel_settings = api_excel_export_settings.create(self.excel_settings)
        api_plan.put_in_excel_settings(self.plan_id, self.created_excel_settings.id)

    def _undo(self):
        api_plan.put_in_excel_settings(self.plan_id, self.old_excel_settings_id)

    def _redo(self):
        api_plan.put_in_excel_settings(self.plan_id, self.created_excel_settings.id)


class PutInExcelExportSettings(Command):
    def __init__(self, plan_id: UUID, excel_settings_id: UUID):
        super().__init__()
        self.plan_id = plan_id
        self.old_excel_settings_id = db_services.Plan.get(plan_id).excel_export_settings.id
        self.excel_settings_id = excel_settings_id

    def execute(self):
        api_plan.put_in_excel_settings(self.plan_id, self.excel_settings_id)

    def _undo(self):
        api_plan.put_in_excel_settings(self.plan_id, self.old_excel_settings_id)

    def _redo(self):
        api_plan.put_in_excel_settings(self.plan_id, self.excel_settings_id)
