from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Update(Command):
    def __init__(self, location_of_work: schemas.LocationOfWorkShow):
        self.new_data = location_of_work.copy()
        self.old_data = db_services.LocationOfWork.get(location_of_work.id)

    def execute(self):
        db_services.LocationOfWork.update(self.new_data)

    def undo(self):
        db_services.LocationOfWork.update(self.old_data)

    def redo(self):
        db_services.LocationOfWork.update(self.new_data)


class NewTimeOfDayStandard(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = db_services.LocationOfWork.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def undo(self):
        db_services.LocationOfWork.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            db_services.LocationOfWork.new_time_of_day_standard(self.location_of_work_id, self.old_t_o_d_standard_id)

    def redo(self):
        db_services.LocationOfWork.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.LocationOfWork.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def undo(self):
        db_services.LocationOfWork.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def redo(self):
        db_services.LocationOfWork.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)