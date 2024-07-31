from commands.command_base_classes import Command
from database import schemas_plan_api, schemas


class WriteProjectToDB(Command):
    def __init__(self, project: schemas_plan_api.Project):
        super().__init__()

        self.project = project
        self.created_project: schemas.ProjectShow | None = None

    def execute(self):
        self.created_project = db_services.Project.create(self.project)

    def undo(self):
        db_services.Project.delete(self.created_project.id)

    def redo(self):
        db_services.Project.undelete(self.created_project.id)