from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Update(Command):
    def __init__(self, person: schemas.PersonShow):
        self.new_data = person.copy()
        self.old_data = db_services.Person.get(person.id)

    def execute(self):
        db_services.Person.update(self.new_data)

    def undo(self):
        db_services.Person.update(self.old_data)

    def redo(self):
        db_services.Person.update(self.new_data)


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
