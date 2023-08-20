from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class UpdateProjectName(Command):
    def __init__(self, new_name: str, project_id: UUID):
        self.new_name = new_name
        self.project_id = project_id
        self.old_name: str = ''

    def execute(self):
        self.old_name = db_services.Project.get(self.project_id).name
        updated_project = db_services.Project.update_name(self.new_name, self.project_id)

    def undo(self):
        updated_project = db_services.Project.update_name(self.old_name, self.project_id)

    def redo(self):
        updated_project = db_services.Project.update_name(self.new_name, self.project_id)

    def __repr__(self):
        return f'{self.old_name=}, {self.new_name=}'


class Update(Command):
    def __init__(self, project: schemas.ProjectShow):
        self.new_data: schemas.ProjectShow = project.model_copy()
        self.old_data: schemas.ProjectShow = db_services.Project.get(project.id)

    def execute(self):
        db_services.Project.update(self.new_data)

    def undo(self):
        db_services.Project.update(self.old_data)

    def redo(self):
        db_services.Project.update(self.new_data)


class PutInTimeOfDay(Command):
    def __init__(self, project_id: UUID, time_of_day_id: UUID):
        self.project_id = project_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Project.put_in_time_of_day(self.project_id, self.time_of_day_id)

    def undo(self):
        db_services.Project.remove_in_time_of_day(self.project_id, self.time_of_day_id)

    def redo(self):
        db_services.Project.put_in_time_of_day(self.project_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, project_id: UUID, time_of_day_id: UUID):
        self.project_id = project_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Project.remove_in_time_of_day(self.project_id, self.time_of_day_id)

    def undo(self):
        db_services.Project.put_in_time_of_day(self.project_id, self.time_of_day_id)

    def redo(self):
        db_services.Project.remove_in_time_of_day(self.project_id, self.time_of_day_id)


class NewTimeOfDayStandard(Command):
    def __init__(self, project_id: UUID, time_of_day_id: UUID):
        self.project_id = project_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = db_services.Project.new_time_of_day_standard(self.project_id, self.time_of_day_id)

    def undo(self):
        db_services.Project.remove_time_of_day_standard(self.project_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            db_services.Project.new_time_of_day_standard(self.project_id, self.old_t_o_d_standard_id)

    def redo(self):
        db_services.Project.new_time_of_day_standard(self.project_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, project_id: UUID, time_of_day_id: UUID):
        self.project_id = project_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Project.remove_time_of_day_standard(self.project_id, self.time_of_day_id)

    def undo(self):
        db_services.Project.new_time_of_day_standard(self.project_id, self.time_of_day_id)

    def redo(self):
        db_services.Project.remove_time_of_day_standard(self.project_id, self.time_of_day_id)