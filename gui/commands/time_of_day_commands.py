from uuid import UUID

from database import schemas, db_services
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, time_of_day: schemas.TimeOfDayCreate, project_id: UUID):
        self.project_id = project_id
        self.new_data = time_of_day.copy()
        self.time_of_day_id: UUID | None = None

    def execute(self):
        created_time_of_day = db_services.TimeOfDay.create(self.new_data, self.project_id)
        self.time_of_day_id = created_time_of_day.id

    def undo(self):
        db_services.TimeOfDay.delete(self.time_of_day_id)

    def redo(self):
        db_services.TimeOfDay.undo_delete(self.time_of_day_id)

    def get_created_time_of_day_id(self):
        return self.time_of_day_id


class Update(Command):
    def __init__(self, time_of_day: schemas.TimeOfDay):
        self.new_data = time_of_day.copy()
        self.old_data = db_services.TimeOfDay.get(time_of_day.id)

    def execute(self):
        db_services.TimeOfDay.update(self.new_data)

    def undo(self):
        db_services.TimeOfDay.update(self.old_data)

    def redo(self):
        db_services.TimeOfDay.update(self.new_data)


class Delete(Command):
    def __init__(self, time_of_day_id: UUID):
        self.time_of_day_id = time_of_day_id
        self.old_data = db_services.TimeOfDay.get(time_of_day_id)

    def execute(self):
        db_services.TimeOfDay.delete(self.time_of_day_id)

    def undo(self):
        db_services.TimeOfDay.undo_delete(self.time_of_day_id)

    def redo(self):
        db_services.TimeOfDay.delete(self.time_of_day_id)
