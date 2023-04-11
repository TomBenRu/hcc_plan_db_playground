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
        self.new_data: schemas.ProjectShow = project.copy()
        self.old_data: schemas.ProjectShow = db_services.Project.get(project.id)

    def execute(self):
        db_services.Project.update(self.new_data)

    def undo(self):
        db_services.Project.update(self.old_data)

    def redo(self):
        db_services.Project.update(self.new_data)
