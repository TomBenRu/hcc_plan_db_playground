"""Command-Klassen für LocationOfWork (Arbeitsort).

Neben einfachen Feldupdates (Tageszeiten, fixed_cast, SkillGroups) enthält dieses
Modul zwei komplexe Commands:

- `AssignToTeam`: Weist einen Standort ab einem Datum einem Team zu. Löscht dabei
  spätere Zuordnungen und passt ggf. das Enddatum der vorherigen Zuweisung an.
  Verwendet intern einen eigenen `ContrExecUndoRedo`-Controller, um alle
  Unter-Commands als eine einzige Undo-Einheit zu kapseln.
- `LeaveTeam`: Beendet die aktive Team-Zuweisung eines Standorts ab einem Datum;
  verwendet denselben Controller-Mechanismus.
"""
import datetime
from uuid import UUID

from database import db_services, schemas
from commands.database_commands import team_location_assignment_commands
from commands.command_base_classes import Command, ContrExecUndoRedo
from gui.api_client import location_of_work as api_low


class Update(Command):
    def __init__(self, location_of_work: schemas.LocationOfWorkShow):
        super().__init__()
        self.new_data = location_of_work.model_copy()
        self.old_data = db_services.LocationOfWork.get(location_of_work.id)
        self.updated_location_of_work: schemas.LocationOfWorkShow | None = None

    def execute(self):
        self.updated_location_of_work = api_low.update(self.new_data)

    def _undo(self):
        api_low.update(self.old_data)

    def _redo(self):
        api_low.update(self.new_data)


class PutInTimeOfDay(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_low.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def _undo(self):
        api_low.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def _redo(self):
        api_low.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_low.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def _undo(self):
        api_low.put_in_time_of_day(self.location_of_work_id, self.time_of_day_id)

    def _redo(self):
        api_low.remove_in_time_of_day(self.location_of_work_id, self.time_of_day_id)


class NewTimeOfDayStandard(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = api_low.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def _undo(self):
        api_low.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            api_low.new_time_of_day_standard(self.location_of_work_id, self.old_t_o_d_standard_id)

    def _redo(self):
        api_low.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, location_of_work_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        api_low.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def _undo(self):
        api_low.new_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)

    def _redo(self):
        api_low.remove_time_of_day_standard(self.location_of_work_id, self.time_of_day_id)


class AssignToTeam(Command):
    def __init__(self, location_id: UUID, team_id: UUID, start: datetime.date):
        super().__init__()
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

    def _undo(self):
        self.controller.undo_all()

    def _redo(self):
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
        super().__init__()
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

    def _undo(self):
        self.controller.undo_all()

    def _redo(self):
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


class UpdateFixedCast(Command):
    def __init__(self, location_of_work_id: UUID, fixed_cast: str | None, fixed_cast_only_if_available: bool):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.fixed_cast = fixed_cast
        self.fixed_cast_only_if_available = fixed_cast_only_if_available
        self.fixed_cast_old: str | None = None
        self.fixed_cast_only_if_available_old: bool = False

    def execute(self):
        location_of_work = db_services.LocationOfWork.get(self.location_of_work_id)
        self.fixed_cast_old = location_of_work.fixed_cast
        self.fixed_cast_only_if_available_old = location_of_work.fixed_cast_only_if_available
        api_low.update_fixed_cast(self.location_of_work_id, self.fixed_cast,
                                                    self.fixed_cast_only_if_available)

    def _undo(self):
        api_low.update_fixed_cast(self.location_of_work_id, self.fixed_cast_old,
                                                    self.fixed_cast_only_if_available_old)

    def _redo(self):
        api_low.update_fixed_cast(self.location_of_work_id, self.fixed_cast,
                                                    self.fixed_cast_only_if_available)


class AddSkillGroup(Command):
    def __init__(self, location_of_work_id: UUID, skill_group_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.skill_group_id = skill_group_id
        self.location_of_work: schemas.LocationOfWorkShow | None = None

    def execute(self):
        self.location_of_work = api_low.add_skill_group(
            self.location_of_work_id, self.skill_group_id)

    def _undo(self):
        if self.location_of_work:
            api_low.remove_skill_group(self.location_of_work_id, self.skill_group_id)

    def _redo(self):
        if self.location_of_work:
            api_low.add_skill_group(self.location_of_work_id, self.skill_group_id)


class RemoveSkillGroup(Command):
    def __init__(self, location_of_work_id: UUID, skill_group_id: UUID):
        super().__init__()
        self.location_of_work_id = location_of_work_id
        self.skill_group_id = skill_group_id
        self.location_of_work: schemas.LocationOfWorkShow | None = None

    def execute(self):
        self.location_of_work = api_low.remove_skill_group(
            self.location_of_work_id, self.skill_group_id)

    def _undo(self):
        if self.location_of_work:
            api_low.add_skill_group(self.location_of_work_id, self.skill_group_id)

    def _redo(self):
        if self.location_of_work:
            api_low.remove_skill_group(self.location_of_work_id, self.skill_group_id)
