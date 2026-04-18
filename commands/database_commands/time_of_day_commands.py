"""Command-Klassen für TimeOfDay (konkrete Tageszeit-Instanz).

Enthält:
- `Create`: Erstellt eine neue Tageszeit; Undo setzt `prep_delete`
  (via `TimeOfDay.delete`), Redo hebt es auf (`undo_delete`).
  Bietet `get_created_time_of_day_id()` für nachfolgende Commands.
- `Update`: Ändert Name, Start, Ende und TimeOfDayEnum; speichert Vorher-Zustand.
- `Delete`: Soft-löscht; Undo via `undo_delete`.
- `DeleteUnusedInProject` / `DeletePrepDeletesInProject`: Cleanup-Aktionen
  mit no-op Undo/Redo. Werden durch die geplante generische DB-Reinigung
  mittelfristig abgelöst (siehe project_general_db_cleanup_planned).
"""
from uuid import UUID

from database import schemas, db_services
from commands.command_base_classes import Command
from gui.api_client import time_of_day as api_time_of_day


class Create(Command):
    def __init__(self, time_of_day: schemas.TimeOfDayCreate, project_id: UUID):
        super().__init__()
        self.project_id = project_id
        self.new_data = time_of_day.model_copy()
        self.time_of_day_id: UUID | None = None

    def execute(self):
        created_time_of_day = db_services.TimeOfDay.create(self.new_data, self.project_id)
        self.time_of_day_id = created_time_of_day.id

    def _undo(self):
        db_services.TimeOfDay.delete(self.time_of_day_id)

    def _redo(self):
        db_services.TimeOfDay.undo_delete(self.time_of_day_id)

    def get_created_time_of_day_id(self):
        return self.time_of_day_id


class Update(Command):
    def __init__(self, time_of_day: schemas.TimeOfDay):
        super().__init__()
        self.new_data = time_of_day.model_copy()
        self.old_data = db_services.TimeOfDay.get(time_of_day.id)

    def execute(self):
        db_services.TimeOfDay.update(self.new_data)

    def _undo(self):
        db_services.TimeOfDay.update(self.old_data)

    def _redo(self):
        db_services.TimeOfDay.update(self.new_data)


class Delete(Command):
    def __init__(self, time_of_day_id: UUID):
        super().__init__()
        self.time_of_day_id = time_of_day_id
        self.old_data = db_services.TimeOfDay.get(time_of_day_id)

    def execute(self):
        db_services.TimeOfDay.delete(self.time_of_day_id)

    def _undo(self):
        db_services.TimeOfDay.undo_delete(self.time_of_day_id)

    def _redo(self):
        db_services.TimeOfDay.delete(self.time_of_day_id)


class DeleteUnusedInProject(Command):
    """Soft-loescht alle unreferenzierten TimeOfDays des Projekts.

    Bulk-Cleanup ohne feine Einzelschritt-Semantik. Undo/Redo sind no-ops —
    Wiederherstellung einzelner orphaned TODs waere teuer und kein
    realistischer User-Flow. Siehe project_general_db_cleanup_planned
    (wird mittelfristig durch generische Reinigung ersetzt).
    """

    def __init__(self, project_id: UUID):
        super().__init__()
        self.project_id = project_id

    def execute(self):
        api_time_of_day.delete_unused_in_project(self.project_id)

    def _undo(self):
        ...

    def _redo(self):
        ...


class DeletePrepDeletesInProject(Command):
    """Hartes Loeschen aller prep-deleted TimeOfDays des Projekts.

    Irreversibel (hard-delete); Undo/Redo no-ops. Wird mittelfristig durch
    generische Reinigung ersetzt.
    """

    def __init__(self, project_id: UUID):
        super().__init__()
        self.project_id = project_id

    def execute(self):
        api_time_of_day.delete_prep_deletes_in_project(self.project_id)

    def _undo(self):
        ...

    def _redo(self):
        ...
