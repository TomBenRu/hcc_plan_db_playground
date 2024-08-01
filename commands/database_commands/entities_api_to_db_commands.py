from uuid import UUID

from commands.command_base_classes import Command
from database import schemas_plan_api, schemas, db_services


class WriteProjectToDB(Command):
    def __init__(self, project: schemas_plan_api.Project):
        super().__init__()

        self.project = project
        self.created_project: schemas.ProjectShow | None = None

    def execute(self):
        self.created_project = db_services.EntitiesApiToDB.create_project(self.project)

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
    def __init__(self, team: schemas_plan_api.Team):
        super().__init__()
        self.team = team
        self.created_team: schemas.TeamShow | None = None

    def execute(self):
        self.created_team = db_services.EntitiesApiToDB.create_team(self.team)

    def undo(self):
        db_services.EntitiesApiToDB.delete_team(self.created_team.id)

    def redo(self):
        raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')


class WritePlanPeriodToDB(Command):
    def __init__(self, plan_period: schemas_plan_api.PlanPeriod, person_ids: set[UUID], location_ids: set[UUID]):
        super().__init__()
        self.plan_period = plan_period
        self.location_ids = location_ids
        self.person_ids = person_ids
        self.created_plan_period: schemas.PlanPeriod | None = None
        self.created_actor_plan_periods: list[schemas.ActorPlanPeriodShow] = []
        self.created_location_plan_periods: list[schemas.LocationPlanPeriodShow] = []

    def execute(self):
        self.created_plan_period = db_services.EntitiesApiToDB.create_plan_period(self.plan_period)
        for person_id in self.person_ids:
            self.created_actor_plan_periods.append(
                db_services.ActorPlanPeriod.create(self.created_plan_period.id, person_id)
            )
            db_services.AvailDayGroup.create(actor_plan_period_id=self.created_actor_plan_periods[-1].id)
        for location_id in self.location_ids:
            self.created_location_plan_periods.append(
                db_services.LocationPlanPeriod.create(self.created_plan_period.id, location_id)
            )
            db_services.EventGroup.create(location_plan_period_id=self.created_location_plan_periods[-1].id)

    def undo(self):
        db_services.EntitiesApiToDB.delete_plan_period(self.created_plan_period.id)

    def redo(self):
        raise NotImplementedError('Aktion kann nicht rückgängig gemacht werden.')
