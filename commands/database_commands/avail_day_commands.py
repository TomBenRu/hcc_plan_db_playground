from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class Create(Command):
    def __init__(self, avail_day: schemas.AvailDayCreate):
        super().__init__()
        self.avail_day = avail_day.model_copy()
        self.created_avail_day: schemas.AvailDayShow | None = None

    def execute(self):
        self.created_avail_day = db_services.AvailDay.create(self.avail_day)

    def _undo(self):
        db_services.AvailDay.delete(self.created_avail_day.id)

    def _redo(self):
        self.created_avail_day = db_services.AvailDay.create(self.avail_day)


class Delete(Command):
    def __init__(self, avail_day_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.avail_day_to_delete = db_services.AvailDay.get(avail_day_id)

    def execute(self):
        db_services.AvailDay.delete(self.avail_day_id)

    def _undo(self):
        """todo: Schwierigkeit: Beim Löschen wurden unter Umständen kaskadenweise AvailDayGroups gelöscht.
           diese können auf diese Weise nicht wiederhergestellt werden."""
        self.avail_day_id = db_services.AvailDay.create(self.avail_day_to_delete).id

    def _redo(self):
        db_services.AvailDay.delete(self.avail_day_id)


class UpdateTimeOfDays(Command):
    def __init__(self, avail_day_id: UUID, time_of_days: list[schemas.TimeOfDay]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.new_time_of_days = time_of_days
        self.old_time_of_days = db_services.AvailDay.get(avail_day_id).time_of_days

    def execute(self):
        db_services.AvailDay.update_time_of_days(self.avail_day_id, self.new_time_of_days)

    def _undo(self):
        db_services.AvailDay.update_time_of_days(self.avail_day_id, self.old_time_of_days)

    def _redo(self):
        db_services.AvailDay.update_time_of_days(self.avail_day_id, self.new_time_of_days)


class UpdateTimeOfDay(Command):
    def __init__(self, avail_day: schemas.AvailDayShow, new_time_of_day_id: UUID):
        super().__init__()
        self.avail_day = avail_day
        self.old_time_of_day_id = self.avail_day.time_of_day.id
        self.new_time_of_day_id = new_time_of_day_id

    def execute(self):
        db_services.AvailDay.update_time_of_day(self.avail_day.id, self.new_time_of_day_id)

    def _undo(self):
        db_services.AvailDay.update_time_of_day(self.avail_day.id, self.old_time_of_day_id)

    def _redo(self):
        db_services.AvailDay.update_time_of_day(self.avail_day.id, self.new_time_of_day_id)


class PutInCombLocPossible(Command):
    def __init__(self, avail_day_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.AvailDay.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def _undo(self):
        db_services.AvailDay.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def _redo(self):
        db_services.AvailDay.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)


class PutInCombLocPossibles(Command):
    def __init__(self, avail_day_id: UUID, comb_loc_poss_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.comb_loc_poss_ids = comb_loc_poss_ids

    def execute(self):
        db_services.AvailDay.put_in_comb_loc_possibles(self.avail_day_id, self.comb_loc_poss_ids)

    def _undo(self):
        for comb_loc_poss_id in self.comb_loc_poss_ids:
            db_services.AvailDay.remove_comb_loc_possible(self.avail_day_id, comb_loc_poss_id)

    def _redo(self):
        db_services.AvailDay.put_in_comb_loc_possibles(self.avail_day_id, self.comb_loc_poss_ids)


class RemoveCombLocPossible(Command):
    def __init__(self, avail_day_id: UUID, comb_loc_poss_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.AvailDay.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def _undo(self):
        db_services.AvailDay.put_in_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)

    def _redo(self):
        db_services.AvailDay.remove_comb_loc_possible(self.avail_day_id, self.comb_loc_poss_id)


class ClearCombLocPossibles(Command):
    def __init__(self, avail_day_id: UUID, existing_comb_loc_poss_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.existing_comb_loc_poss_ids = existing_comb_loc_poss_ids

    def execute(self):
        db_services.AvailDay.clear_comb_loc_possibles(self.avail_day_id)

    def _undo(self):
        db_services.AvailDay.put_in_comb_loc_possibles(self.avail_day_id, self.existing_comb_loc_poss_ids)

    def _redo(self):
        db_services.AvailDay.clear_comb_loc_possibles(self.avail_day_id)


class PutInActorLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.AvailDay.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def _undo(self):
        db_services.AvailDay.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def _redo(self):
        db_services.AvailDay.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)


class PutInActorLocationPrefs(Command):
    def __init__(self, avail_day_id: UUID, actor_loc_pref_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_loc_pref_ids = actor_loc_pref_ids

    def execute(self):
        db_services.AvailDay.put_in_location_prefs(self.avail_day_id, self.actor_loc_pref_ids)

    def _undo(self):
        for actor_loc_pref_id in self.actor_loc_pref_ids:
            db_services.AvailDay.remove_location_pref(self.avail_day_id, actor_loc_pref_id)

    def _redo(self):
        db_services.AvailDay.put_in_location_prefs(self.avail_day_id, self.actor_loc_pref_ids)


class RemoveActorLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_loc_pref_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.AvailDay.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def _undo(self):
        db_services.AvailDay.put_in_location_pref(self.avail_day_id, self.actor_loc_pref_id)

    def _redo(self):
        db_services.AvailDay.remove_location_pref(self.avail_day_id, self.actor_loc_pref_id)


class ClearActorLocationPrefs(Command):
    def __init__(self, avail_day_id: UUID, existing_actor_loc_pref_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.existing_actor_loc_pref_ids = existing_actor_loc_pref_ids

    def execute(self):
        db_services.AvailDay.clear_location_prefs(self.avail_day_id)

    def _undo(self):
        db_services.AvailDay.put_in_location_prefs(self.avail_day_id, self.existing_actor_loc_pref_ids)

    def _redo(self):
        db_services.AvailDay.clear_location_prefs(self.avail_day_id)


class PutInActorPartnerLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.AvailDay.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def _undo(self):
        db_services.AvailDay.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def _redo(self):
        db_services.AvailDay.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)


class PutInActorPartnerLocationPrefs(Command):
    def __init__(self, avail_day_id: UUID, actor_partner_loc_pref_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_partner_loc_pref_ids = actor_partner_loc_pref_ids

    def execute(self):
        db_services.AvailDay.put_in_partner_location_prefs(self.avail_day_id, self.actor_partner_loc_pref_ids)

    def _undo(self):
        for actor_partner_loc_pref_id in self.actor_partner_loc_pref_ids:
            db_services.AvailDay.remove_partner_location_pref(self.avail_day_id, actor_partner_loc_pref_id)

    def _redo(self):
        db_services.AvailDay.put_in_partner_location_prefs(self.avail_day_id, self.actor_partner_loc_pref_ids)


class RemoveActorPartnerLocationPref(Command):
    def __init__(self, avail_day_id: UUID, actor_partner_loc_pref_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.AvailDay.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def _undo(self):
        db_services.AvailDay.put_in_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)

    def _redo(self):
        db_services.AvailDay.remove_partner_location_pref(self.avail_day_id, self.actor_partner_loc_pref_id)


class ClearActorPartnerLocationPrefs(Command):
    def __init__(self, avail_day_id: UUID, existing_actor_partner_loc_pref_ids: list[UUID]):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.existing_actor_partner_loc_pref_ids = existing_actor_partner_loc_pref_ids

    def execute(self):
        db_services.AvailDay.clear_partner_location_prefs(self.avail_day_id)

    def _undo(self):
        db_services.AvailDay.put_in_partner_location_prefs(self.avail_day_id, self.existing_actor_partner_loc_pref_ids)

    def _redo(self):
        db_services.AvailDay.clear_partner_location_prefs(self.avail_day_id)



class AddSkill(Command):
    def __init__(self, avail_day_id: UUID, skill_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.skill_id = skill_id
        self.updated_object: schemas.PersonShow | None = None

    def execute(self):
        self.updated_object = db_services.AvailDay.add_skill(self.avail_day_id, self.skill_id)

    def _undo(self):
        if self.updated_object:
            db_services.AvailDay.remove_skill(self.updated_object.id, self.skill_id)

    def _redo(self):
        if self.updated_object:
            db_services.AvailDay.add_skill(self.updated_object.id, self.skill_id)

class RemoveSkill(Command):
    def __init__(self, avail_day_id: UUID, skill_id: UUID):
        super().__init__()
        self.avail_day_id = avail_day_id
        self.skill_id = skill_id
        self.updated_object: schemas.AvailDayShow | None = None

    def execute(self):
        self.updated_object = db_services.AvailDay.remove_skill(self.avail_day_id, self.skill_id)

    def _undo(self):
        if self.updated_object:
            db_services.AvailDay.add_skill(self.updated_object.id, self.skill_id)

    def _redo(self):
        if self.updated_object:
            db_services.AvailDay.remove_skill(self.updated_object.id, self.skill_id)
