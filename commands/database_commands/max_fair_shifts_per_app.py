"""Command-Klassen für MaxFairShiftsOfApp (Max./faire Einsätze je ActorPlanPeriod).

Enthält:
- `Create`: Erstellt einen neuen Fairness-Grenzwert-Eintrag für eine ActorPlanPeriod.
  Nach dem Erstellen wird die generierte ID ins Schema zurückgeschrieben, damit Redo
  dieselbe ID wiederverwenden kann.
"""
from commands.command_base_classes import Command
from database import schemas, db_services


class Create(Command):
    def __init__(self, max_fair_shifts_per_app: schemas.MaxFairShiftsOfAppCreate):
        super().__init__()
        self.max_fair_shifts_per_app = max_fair_shifts_per_app
        self.created_max_fair_shifts_per_app: schemas.MaxFairShiftsOfAppShow | None = None

    def execute(self):
        self.created_max_fair_shifts_per_app = db_services.MaxFairShiftsOfApp.create(self.max_fair_shifts_per_app)
        self.max_fair_shifts_per_app.id = self.created_max_fair_shifts_per_app.id

    def _undo(self):
        db_services.MaxFairShiftsOfApp.delete(self.created_max_fair_shifts_per_app.id)

    def _redo(self):
        db_services.MaxFairShiftsOfApp.create(self.max_fair_shifts_per_app)
