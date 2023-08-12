import datetime
from uuid import UUID

from database import db_services, schemas
from gui.commands import team_actor_assignment_commands
from gui.commands.command_base_classes import Command, ContrExecUndoRedo


class Update(Command):
    def __init__(self, person: schemas.PersonShow):
        self.new_data = person.model_copy()
        self.old_data = db_services.Person.get(person.id)

    def execute(self):
        db_services.Person.update(self.new_data)

    def undo(self):
        db_services.Person.update(self.old_data)

    def redo(self):
        db_services.Person.update(self.new_data)


class PutInTimeOfDay(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Person.put_in_time_of_day(self.person_id, self.time_of_day_id)

    def undo(self):
        db_services.Person.remove_in_time_of_day(self.person_id, self.time_of_day_id)

    def redo(self):
        db_services.Person.put_in_time_of_day(self.person_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Person.remove_in_time_of_day(self.person_id, self.time_of_day_id)

    def undo(self):
        db_services.Person.put_in_time_of_day(self.person_id, self.time_of_day_id)

    def redo(self):
        db_services.Person.remove_in_time_of_day(self.person_id, self.time_of_day_id)


class NewTimeOfDayStandard(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = db_services.Person.new_time_of_day_standard(self.person_id, self.time_of_day_id)

    def undo(self):
        db_services.Person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            db_services.Person.new_time_of_day_standard(self.person_id, self.old_t_o_d_standard_id)

    def redo(self):
        db_services.Person.new_time_of_day_standard(self.person_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)

    def undo(self):
        db_services.Person.new_time_of_day_standard(self.person_id, self.time_of_day_id)

    def redo(self):
        db_services.Person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)


class PutInCombLocPossible(Command):
    def __init__(self, person_id: UUID, comb_loc_poss_id: UUID):

        self.person_id = person_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.Person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.Person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.Person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, person_id: UUID, comb_loc_poss_id: UUID):

        self.person_id = person_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.Person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.Person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.Person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)


class PutInActorLocationPref(Command):
    def __init__(self, person_id: UUID, actor_loc_pref_id: UUID):

        self.person_id = person_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.Person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)

    def undo(self):
        db_services.Person.remove_location_pref(self.person_id, self.actor_loc_pref_id)

    def redo(self):
        db_services.Person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)


class RemoveActorLocationPref(Command):
    def __init__(self, person_id: UUID, actor_loc_pref_id: UUID):

        self.person_id = person_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.Person.remove_location_pref(self.person_id, self.actor_loc_pref_id)

    def undo(self):
        db_services.Person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)

    def redo(self):
        db_services.Person.remove_location_pref(self.person_id, self.actor_loc_pref_id)


class PutInActorPartnerLocationPref(Command):
    def __init__(self, person_id: UUID, actor_partner_loc_pref_id: UUID):

        self.person_id = person_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.Person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def undo(self):
        db_services.Person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def redo(self):
        db_services.Person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)


class RemoveActorPartnerLocationPref(Command):
    def __init__(self, person_id: UUID, actor_partner_loc_pref_id: UUID):

        self.person_id = person_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.Person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def undo(self):
        db_services.Person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def redo(self):
        db_services.Person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)


class AssignToTeam(Command):
    def __init__(self, person_id: UUID, team_id: UUID, start: datetime.date):
        self.person_id = person_id
        self.team_id = team_id
        self.person = db_services.Person.get(person_id)
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

    def get_assignments_later_than_start(self) -> list[schemas.TeamActorAssign]:
        return [a for a in self.person.team_actor_assigns if a.start >= self.start]

    def get_latest_assignment_before_start(self) -> schemas.TeamActorAssign | None:
        assignments_before_start = [a for a in self.person.team_actor_assigns if a.start < self.start]
        return max(assignments_before_start, key=lambda x: x.start) if assignments_before_start else None

    def change_assignm_end_date(self, assignm_id: UUID, end_date: datetime.date | None):
        command = team_actor_assignment_commands.ChangeEndDate(assignm_id, end_date)
        self.controller.execute(command)

    def create_assignment(self):
        command = team_actor_assignment_commands.Create(self.person_id, self.team_id, self.start)
        self.controller.execute(command)

    def delete_assignments(self, assignments: list[schemas.TeamActorAssign]):
        for assignm in assignments:
            delete_command = team_actor_assignment_commands.Delete(assignm.id)
            self.controller.execute(delete_command)


class LeaveTeam(Command):
    def __init__(self, person_id: UUID, start: datetime.date):
        self.person_id = person_id
        self.person = db_services.Person.get(person_id)
        self.start = start

        self.controller = ContrExecUndoRedo()

    def execute(self):
        if not self.person.team_actor_assigns:
            raise LookupError('Location ist keinem Team zugeordnet.')
        self.delete_assignments(self.get_assignments_later_than_start())
        latest_assignment = self.get_latest_assignment_before_start()
        if latest_assignment and (latest_assignment.end is None or latest_assignment.end > self.start):
            self.change_assignm_end_date(latest_assignment.id, self.start)

    def undo(self):
        self.controller.undo_all()

    def redo(self):
        self.execute()

    def get_assignments_later_than_start(self) -> list[schemas.TeamActorAssign]:
        return [a for a in self.person.team_actor_assigns if a.start >= self.start]

    def get_latest_assignment_before_start(self) -> schemas.TeamActorAssign | None:
        assignments_before_start = [a for a in self.person.team_actor_assigns if a.start < self.start]
        return max(assignments_before_start, key=lambda x: x.start) if assignments_before_start else None

    def delete_assignments(self, assignments: list[schemas.TeamActorAssign]):
        for assignm in assignments:
            delete_command = team_actor_assignment_commands.Delete(assignm.id)
            self.controller.execute(delete_command)

    def change_assignm_end_date(self, assignm_id: UUID, end_date: datetime.date | None):
        command = team_actor_assignment_commands.ChangeEndDate(assignm_id, end_date)
        self.controller.execute(command)
