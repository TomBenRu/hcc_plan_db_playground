import datetime
from uuid import UUID

from database import db_services, schemas, special_schema_requests
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


class AssignToTeam(Command):
    def __init__(self, location_id: UUID, team_id: UUID | None, start: datetime.date):
        self.location = db_services.LocationOfWork.get(location_id)
        self.location_id = location_id
        self.team_id = team_id
        self.start = start
        self.created_assignment: schemas.TeamLocationAssignShow | None = None
        self.latest_assignment = max(self.location.team_location_assigns, key=lambda x: x.start) if self.location.team_location_assigns else None

    def execute(self):
        if self.team_id:
            self.created_assignment = db_services.LocationOfWork.assign_to_team(
                self.location_id, self.team_id, self.start)
        else:
            db_services.LocationOfWork.remove_from_team(self.location_id, self.start)

    def undo(self):
        if self.team_id:
            if self.created_assignment:
                db_services.TeamLocationAssign.delete(self.created_assignment.id)
                if self.latest_assignment:
                    if self.latest_assignment.end:
                        db_services.LocationOfWork.remove_from_team(self.location_id, self.latest_assignment.end)
                    else:
                        db_services.TeamLocationAssign.set_end_to_none(self.latest_assignment.id)
        elif self.latest_assignment.end:
            db_services.LocationOfWork.remove_from_team(self.location_id, self.latest_assignment.end)
        else:
            db_services.TeamLocationAssign.set_end_to_none(self.latest_assignment.id)

    def redo(self):
        self.created_assignment = db_services.LocationOfWork.assign_to_team(self.location_id, self.team_id, self.start)
