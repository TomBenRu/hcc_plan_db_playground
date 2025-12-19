import datetime
from uuid import UUID

from database import db_services, schemas
from commands.database_commands import team_actor_assignment_commands
from commands.command_base_classes import Command, ContrExecUndoRedo


class Create(Command):
    def __init__(self, person: schemas.PersonCreate, project_id: UUID):
        super().__init__()
        self.person = person
        self.project_id = project_id
        self.created_person: schemas.PersonShow | None = None

    def execute(self):
        self.created_person = db_services.Person.create(self.person, self.project_id)

    def _undo(self):
        if self.created_person:
            db_services.Person.delete(self.created_person.id)

    def _redo(self):
        if self.created_person:
            db_services.Person.create(self.person, self.project_id, self.created_person.id)



class Update(Command):
    def __init__(self, person: schemas.PersonShow):
        super().__init__()
        self.new_data = person.model_copy()
        self.old_data = db_services.Person.get(person.id)
        self.updated_person: schemas.Person | None = None

    def execute(self):
        self.updated_person = db_services.Person.update(self.new_data)

    def _undo(self):
        db_services.Person.update(self.old_data)

    def _redo(self):
        db_services.Person.update(self.new_data)


class PutInTimeOfDay(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Person.put_in_time_of_day(self.person_id, self.time_of_day_id)

    def _undo(self):
        db_services.Person.remove_in_time_of_day(self.person_id, self.time_of_day_id)

    def _redo(self):
        db_services.Person.put_in_time_of_day(self.person_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Person.remove_in_time_of_day(self.person_id, self.time_of_day_id)

    def _undo(self):
        db_services.Person.put_in_time_of_day(self.person_id, self.time_of_day_id)

    def _redo(self):
        db_services.Person.remove_in_time_of_day(self.person_id, self.time_of_day_id)


class NewTimeOfDayStandard(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = db_services.Person.new_time_of_day_standard(self.person_id, self.time_of_day_id)

    def _undo(self):
        db_services.Person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            db_services.Person.new_time_of_day_standard(self.person_id, self.old_t_o_d_standard_id)

    def _redo(self):
        db_services.Person.new_time_of_day_standard(self.person_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, person_id: UUID, time_of_day_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.Person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)

    def _undo(self):
        db_services.Person.new_time_of_day_standard(self.person_id, self.time_of_day_id)

    def _redo(self):
        db_services.Person.remove_time_of_day_standard(self.person_id, self.time_of_day_id)


class PutInCombLocPossible(Command):
    def __init__(self, person_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.Person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def _undo(self):
        db_services.Person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def _redo(self):
        db_services.Person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, person_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.Person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def _undo(self):
        db_services.Person.put_in_comb_loc_possible(self.person_id, self.comb_loc_poss_id)

    def _redo(self):
        db_services.Person.remove_comb_loc_possible(self.person_id, self.comb_loc_poss_id)


class PutInActorLocationPref(Command):
    def __init__(self, person_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.Person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)

    def _undo(self):
        db_services.Person.remove_location_pref(self.person_id, self.actor_loc_pref_id)

    def _redo(self):
        db_services.Person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)


class RemoveActorLocationPref(Command):
    def __init__(self, person_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.Person.remove_location_pref(self.person_id, self.actor_loc_pref_id)

    def _undo(self):
        db_services.Person.put_in_location_pref(self.person_id, self.actor_loc_pref_id)

    def _redo(self):
        db_services.Person.remove_location_pref(self.person_id, self.actor_loc_pref_id)


class PutInActorPartnerLocationPref(Command):
    def __init__(self, person_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.Person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def _undo(self):
        db_services.Person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def _redo(self):
        db_services.Person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)


class RemoveActorPartnerLocationPref(Command):
    def __init__(self, person_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.Person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def _undo(self):
        db_services.Person.put_in_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)

    def _redo(self):
        db_services.Person.remove_partner_location_pref(self.person_id, self.actor_partner_loc_pref_id)


class AssignToTeam(Command):
    # todo: ActorPlanPeriods für alle PlanPeriods des Teams ab start hinzufügen.
    def __init__(self, person_id: UUID, team_id: UUID, start: datetime.date):
        super().__init__()
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

    def _undo(self):
        self.controller.undo_all()

    def _redo(self):
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
        super().__init__()
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

    def _undo(self):
        self.controller.undo_all()

    def _redo(self):
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


class PutInFlag(Command):
    def __init__(self, person_id: UUID, flag_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.flag_id = flag_id

    def execute(self):
        db_services.Person.put_in_flag(self.person_id, self.flag_id)

    def _undo(self):
        db_services.Person.remove_flag(self.person_id, self.flag_id)

    def _redo(self):
        db_services.Person.put_in_flag(self.person_id, self.flag_id)


class RemoveFlag(Command):
    def __init__(self, person_id: UUID, flag_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.flag_id = flag_id

    def execute(self):
        db_services.Person.remove_flag(self.person_id, self.flag_id)

    def _undo(self):
        db_services.Person.put_in_flag(self.person_id, self.flag_id)

    def _redo(self):
        db_services.Person.remove_flag(self.person_id, self.flag_id)

class AddSkill(Command):
    def __init__(self, person_id: UUID, skill_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.skill_id = skill_id
        self.updated_object: schemas.PersonShow | None = None

    def execute(self):
        self.updated_object = db_services.Person.add_skill(self.person_id, self.skill_id)

    def _undo(self):
        if self.updated_object:
            self.updated_object = db_services.Person.remove_skill(self.updated_object.id, self.skill_id)

    def _redo(self):
        if self.updated_object:
            self.updated_object = db_services.Person.add_skill(self.updated_object.id, self.skill_id)

class RemoveSkill(Command):
    def __init__(self, person_id: UUID, skill_id: UUID):
        super().__init__()
        self.person_id = person_id
        self.skill_id = skill_id
        self.updated_object: schemas.PersonShow | None = None

    def execute(self):
        self.updated_object = db_services.Person.remove_skill(self.person_id, self.skill_id)

    def _undo(self):
        if self.updated_object:
            self.updated_object = db_services.Person.add_skill(self.updated_object.id, self.skill_id)

    def _redo(self):
        if self.updated_object:
            self.updated_object = db_services.Person.remove_skill(self.updated_object.id, self.skill_id)
