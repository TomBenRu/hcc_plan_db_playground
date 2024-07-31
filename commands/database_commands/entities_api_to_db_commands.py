from commands.command_base_classes import Command
from database import schemas_plan_api, schemas, db_services


class WriteProjectToDB(Command):
    def __init__(self, project: schemas_plan_api.Project):
        super().__init__()

        self.project = project
        self.created_project: schemas.ProjectShow | None = None

    def execute(self):
        self.created_project = db_services.EntitiesApiToDB.create_project.create(self.project)

    def undo(self):
        db_services.EntitiesApiToDB.delete_project(self.created_project.id)

    def redo(self):
        raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')


class WritePersonToDB(Command):
    def __init__(self, person: schemas_plan_api.PersonShow):
        super().__init__()
        self.person = person
        self.created_person: schemas.PersonShow | None = None

    def execute(self):
        self.created_person = db_services.EntitiesApiToDB.create_person(self.person)

    def undo(self):
        db_services.EntitiesApiToDB.delete_person(self.created_person.id)

    def redo(self):
        raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')


class WriteTeamToDB(Command):
    def __init__(self):
