from commands.command_base_classes import Command
from database import schemas, db_services


class Create(Command):
    def __init__(self, max_fair_shifts_per_app: schemas.MaxFairShiftsOfAppCreate):
        self.max_fair_shifts_per_app = max_fair_shifts_per_app
        self.created_max_fair_shifts_per_app: schemas.MaxFairShiftsOfAppShow | None = None

    def execute(self):
        self.created_max_fair_shifts_per_app = db_services.MaxFairShiftsOfApp.create(self.max_fair_shifts_per_app)
        self.max_fair_shifts_per_app.id = self.created_max_fair_shifts_per_app.id

    def undo(self):
        db_services.MaxFairShiftsOfApp.delete(self.created_max_fair_shifts_per_app.id)

    def redo(self):
        db_services.MaxFairShiftsOfApp.create(self.max_fair_shifts_per_app)
