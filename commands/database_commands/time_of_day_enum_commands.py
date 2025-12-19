from uuid import UUID

from database import schemas, db_services
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, time_of_day_enum: schemas.TimeOfDayEnumCreate):
        super().__init__()
        self.time_of_day_enum = time_of_day_enum.model_copy()
        self.created_time_of_day_enum_id: UUID | None = None

    def execute(self):
        created_time_of_day_enum = db_services.TimeOfDayEnum.create(self.time_of_day_enum)
        self.created_time_of_day_enum_id = created_time_of_day_enum.id

    def _undo(self):
        db_services.TimeOfDayEnum.delete(self.created_time_of_day_enum_id)

    def _redo(self):
        db_services.TimeOfDayEnum.create(self.time_of_day_enum, self.created_time_of_day_enum_id)

    def get_created_time_of_day_enum_id(self):
        return self.created_time_of_day_enum_id


class Update(Command):
    def __init__(self, time_of_day_enum: schemas.TimeOfDayEnum):
        super().__init__()
        self.time_of_day_enum = time_of_day_enum
        self.old_time_of_day_enum = db_services.TimeOfDayEnum.get(time_of_day_enum.id)

    def execute(self):
        db_services.TimeOfDayEnum.update(self.time_of_day_enum)

    def _undo(self):
        db_services.TimeOfDayEnum.update(self.old_time_of_day_enum)

    def _redo(self):
        db_services.TimeOfDayEnum.update(self.time_of_day_enum)


class PrepDelete(Command):
    def __init__(self, time_of_day_enum_id: UUID):
        super().__init__()
        self.time_of_day_enum_id = time_of_day_enum_id

    def execute(self):
        db_services.TimeOfDayEnum.prep_delete(self.time_of_day_enum_id)

    def _undo(self):
        db_services.TimeOfDayEnum.undo_prep_delete(self.time_of_day_enum_id)

    def _redo(self):
        db_services.TimeOfDayEnum.prep_delete(self.time_of_day_enum_id)
