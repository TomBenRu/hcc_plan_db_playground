import datetime
from uuid import UUID

from database import db_services, schemas, special_schema_requests
from gui.commands import team_location_assignment_commands
from gui.commands.command_base_classes import Command, ContrExecUndoRedo


class Update(Command):
    def __init__(self, location_of_work: schemas.LocationOfWorkShow):
        self.new_data = location_of_work.model_copy()
        self.old_data = db_services.LocationOfWork.get(location_of_work.id)

    def execute(self):
        db_services.LocationOfWork.update(self.new_data)

    def undo(self):
        db_services.LocationOfWork.update(self.old_data)

    def redo(self):
        db_services.LocationOfWork.update(self.new_data)


class PutInTimeOfDay(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.LocationOfWork.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def undo(self):
        db_services.LocationOfWork.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def redo(self):
        db_services.LocationOfWork.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.LocationOfWork.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def undo(self):
        db_services.LocationOfWork.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def redo(self):
        db_services.LocationOfWork.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)


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
    def __init__(self, location_id: UUID, team_id: UUID, start: datetime.date):
        self.location_id = location_id
        self.team_id = team_id
        self.location = db_services.LocationOfWork.get(location_id)
        self.start = start

        self.controller = ContrExecUndoRedo()

    def execute(self):
        if assignments := self.get_assignments_later_than_start():
            self.delete_assignments(assignments)

        if latest_assignment := self.get_latest_assignment_before_start():
            if latest_assignment.end is None or latest_assignment.end >= self.start:
                if latest_assignment.team.id == self.team_id:
                    self.change_assignm_end_date(latest_assignment.id, None)
                else:
                    self.create_assignment()
                    self.change_assignm_end_date(latest_assignment.id, self.start)
            else:
                self.create_assignment()
        else:
            self.create_assignment()

    def undo(self):
        self.controller.undo_all()

    def redo(self):
        self.execute()

    def get_assignments_later_than_start(self) -> list[schemas.TeamLocationAssign]:
        return [a for a in self.location.team_location_assigns if a.start >= self.start]

    def get_latest_assignment_before_start(self) -> schemas.TeamLocationAssign | None:
        assignments_before_start = [a for a in self.location.team_location_assigns if a.start < self.start]
        return max(assignments_before_start, key=lambda x: x.start) if assignments_before_start else None

    def change_assignm_end_date(self, assignm_id: UUID, end_date: datetime.date | None):
        command = team_location_assignment_commands.ChangeEndDate(assignm_id, end_date)
        self.controller.execute(command)

    def create_assignment(self):
        command = team_location_assignment_commands.Create(self.location_id, self.team_id, self.start)
        self.controller.execute(command)

    def delete_assignments(self, assignments: list[schemas.TeamLocationAssign]):
        for assignm in assignments:
            delete_command = team_location_assignment_commands.Delete(assignm.id)
            self.controller.execute(delete_command)


class LeaveTeam(Command):
    def __init__(self, location_id: UUID, start: datetime.date):
        self.location_id = location_id
        self.location = db_services.LocationOfWork.get(location_id)
        self.start = start

        self.controller = ContrExecUndoRedo()

    def execute(self):
        if not self.location.team_location_assigns:
            raise LookupError('Location ist keinem Team zugeordnet.')
        self.delete_assignments(self.get_assignments_later_than_start())
        latest_assignment = self.get_latest_assignment_before_start()
        if latest_assignment and (latest_assignment.end is None or latest_assignment.end > self.start):
            self.change_assignm_end_date(latest_assignment.id, self.start)

    def undo(self):
        self.controller.undo_all()

    def redo(self):
        self.execute()

    def get_assignments_later_than_start(self) -> list[schemas.TeamLocationAssign]:
        return [a for a in self.location.team_location_assigns if a.start >= self.start]

    def get_latest_assignment_before_start(self) -> schemas.TeamLocationAssign | None:
        assignments_before_start = [a for a in self.location.team_location_assigns if a.start < self.start]
        return max(assignments_before_start, key=lambda x: x.start) if assignments_before_start else None

    def delete_assignments(self, assignments: list[schemas.TeamLocationAssign]):
        for assignm in assignments:
            delete_command = team_location_assignment_commands.Delete(assignm.id)
            self.controller.execute(delete_command)

    def change_assignm_end_date(self, assignm_id: UUID, end_date: datetime.date | None):
        command = team_location_assignment_commands.ChangeEndDate(assignm_id, end_date)
        self.controller.execute(command)
