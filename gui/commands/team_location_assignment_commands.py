import datetime
from uuid import UUID

from database import db_services, schemas, special_schema_requests
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, location_id, team_id, start: datetime.date):
        self.start = start
        self.location = db_services.LocationOfWork.get(location_id)
        self.team = db_services.Team.get(team_id)
        self.created_team_loc_assign: schemas.TeamLocationAssign | None = None

    def execute(self):
        tla = schemas.TeamLocationAssignCreate(start=self.start, end=None, location_of_work=self.location,
                                               team=self.team)
        self.created_team_loc_assign = db_services.TeamLocationAssign.create(tla)

    def undo(self):
        db_services.TeamLocationAssign.delete(self.created_team_loc_assign.id)

    def redo(self):
        self.execute()


class ChangeEndDate(Command):
    def __init__(self, assignment_id: UUID, end_date: datetime.date | None):
        self.assignment_id = assignment_id
        self.end_date = end_date
        self.old_end_date = db_services.TeamLocationAssign.get(assignment_id).end

    def execute(self):
        db_services.TeamLocationAssign.set_end_date(self.assignment_id, self.end_date)

    def undo(self):
        db_services.TeamLocationAssign.set_end_date(self.assignment_id, self.old_end_date)

    def redo(self):
        self.execute()

class Delete(Command):
    def __init__(self, assignment_id: UUID):
        self.assignment_id = assignment_id
        self.assignment = db_services.TeamLocationAssign.get(assignment_id)


    def execute(self):
        db_services.TeamLocationAssign.delete(self.assignment_id)

    def undo(self):
        db_services.TeamLocationAssign.create(schemas.TeamLocationAssignCreate(**self.assignment.dict()),
                                              self.assignment_id)

    def redo(self):
        self.execute()