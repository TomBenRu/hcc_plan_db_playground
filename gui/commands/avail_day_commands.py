from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Create(Command):
    def __init__(self, avail_day: schemas.AvailDayCreate):
        self.avail_day = avail_day.copy()
        self.created_avail_day: schemas.AvailDayShow | None = None

    def execute(self):
        self.created_avail_day = db_services.AvailDay.create(self.avail_day)

    def undo(self):
        db_services.AvailDay.delete(self.created_avail_day.id)

    def redo(self):
        self.created_avail_day = db_services.AvailDay.create(self.avail_day)


class Delete(Command):
    def __init__(self, avail_day_id: UUID):
        self.avail_day_id = avail_day_id
        self.deleted_avail_day = db_services.AvailDay.get(avail_day_id)

    def execute(self):
        db_services.AvailDay.delete(self.avail_day_id)

    def undo(self):
        """todo: Schwierigkeit: Beim Löschen wurden unter Umständen kaskadenweise AvailDayGroups gelöscht.
           diese können auf diese Weise nicht wiederhergestellt werden."""
        self.avail_day_id = db_services.AvailDay.create(self.deleted_avail_day).id

    def redo(self):
        db_services.AvailDay.delete(self.avail_day_id)


class UpdateTimeOfDays(Command):
    def __init__(self, avail_day_id: UUID, time_of_days: list[schemas.TimeOfDay]):
        self.avail_day_id = avail_day_id
        self.new_time_of_days = time_of_days
        self.old_time_of_days = db_services.AvailDay.get(avail_day_id).time_of_days

    def execute(self):
        db_services.AvailDay.update_time_of_days(self.avail_day_id, self.new_time_of_days)

    def undo(self):
        db_services.AvailDay.update_time_of_days(self.avail_day_id, self.old_time_of_days)

    def redo(self):
        db_services.AvailDay.update_time_of_days(self.avail_day_id, self.new_time_of_days)


class UpdateTimeOfDay(Command):
    def __init__(self, avail_day: schemas.AvailDayShow, new_time_of_day_id: UUID):
        self.avail_day = avail_day
        self.old_time_of_day_id = self.avail_day.time_of_day.id
        self.new_time_of_day_id = new_time_of_day_id

    def execute(self):
        db_services.AvailDay.update_time_of_day(self.avail_day.id, self.new_time_of_day_id)

    def undo(self):
        db_services.AvailDay.update_time_of_day(self.avail_day.id, self.old_time_of_day_id)

    def redo(self):
        db_services.AvailDay.update_time_of_day(self.avail_day.id, self.new_time_of_day_id)


class PutInCombLocPossible(Command):
    def __init__(self, avail_day_id: UUID, comb_loc_poss_id: UUID):

        self.avail_day_id = avail_day_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.AvailDay.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.AvailDay.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.AvailDay.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, avail_day_id: UUID, comb_loc_poss_id: UUID):

        self.avail_day_id = avail_day_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.AvailDay.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.AvailDay.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.AvailDay.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)


class PutInActorLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_loc_pref_id: UUID):

        self.avail_day_id = avail_day_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.AvailDay.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def undo(self):
        db_services.AvailDay.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def redo(self):
        db_services.AvailDay.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)


class RemoveActorLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_loc_pref_id: UUID):

        self.avail_day_id = avail_day_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.AvailDay.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def undo(self):
        db_services.AvailDay.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def redo(self):
        db_services.AvailDay.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)


class PutInActorPartnerLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_partner_loc_pref_id: UUID):

        self.avail_day_id = avail_day_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.AvailDay.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def undo(self):
        db_services.AvailDay.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def redo(self):
        db_services.AvailDay.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)


class RemoveActorPartnerLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_partner_loc_pref_id: UUID):

        self.avail_day_id = avail_day_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.AvailDay.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def undo(self):
        db_services.AvailDay.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def redo(self):
        db_services.AvailDay.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)
