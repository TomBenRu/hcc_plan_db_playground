from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class PutInTimeOfDay(Command):
    def __init__(self, location_plan_period_id: UUID, time_of_day_id: UUID):
        self.location_plan_period_id = location_plan_period_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.LocationPlanPeriod.put_in_time_of_day(self.location_plan_period_id, self.time_of_day_id)

    def undo(self):
        db_services.LocationPlanPeriod.remove_in_time_of_day(self.location_plan_period_id, self.time_of_day_id)

    def redo(self):
        db_services.LocationPlanPeriod.put_in_time_of_day(self.location_plan_period_id, self.time_of_day_id)


class RemoveTimeOfDay(Command):
    def __init__(self, location_plan_period_id: UUID, time_of_day_id: UUID):
        self.location_plan_period_id = location_plan_period_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.LocationPlanPeriod.remove_in_time_of_day(self.location_plan_period_id, self.time_of_day_id)

    def undo(self):
        db_services.LocationPlanPeriod.put_in_time_of_day(self.location_plan_period_id, self.time_of_day_id)

    def redo(self):
        db_services.LocationPlanPeriod.remove_in_time_of_day(self.location_plan_period_id, self.time_of_day_id)


class NewTimeOfDayStandard(Command):
    def __init__(self, location_plan_period_id: UUID, time_of_day_id: UUID):
        self.location_plan_period_id = location_plan_period_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = db_services.LocationPlanPeriod.new_time_of_day_standard(
            self.location_plan_period_id, self.time_of_day_id)

    def undo(self):
        db_services.LocationPlanPeriod.remove_time_of_day_standard(self.location_plan_period_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            db_services.LocationPlanPeriod.new_time_of_day_standard(self.location_plan_period_id,
                                                                    self.old_t_o_d_standard_id)

    def redo(self):
        db_services.LocationPlanPeriod.new_time_of_day_standard(self.location_plan_period_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, location_plan_period_id: UUID, time_of_day_id: UUID):
        self.location_plan_period_id = location_plan_period_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.LocationPlanPeriod.remove_time_of_day_standard(self.location_plan_period_id, self.time_of_day_id)

    def undo(self):
        db_services.LocationPlanPeriod.new_time_of_day_standard(self.location_plan_period_id, self.time_of_day_id)

    def redo(self):
        db_services.LocationPlanPeriod.remove_time_of_day_standard(self.location_plan_period_id, self.time_of_day_id)


class PutInCombLocPossible(Command):
    def __init__(self, actor_plan_period_id: UUID, comb_loc_poss_id: UUID):

        self.actor_plan_period_id = actor_plan_period_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.ActorPlanPeriod.put_in_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.ActorPlanPeriod.remove_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.ActorPlanPeriod.put_in_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)


class RemoveCombLocPossible(Command):
    def __init__(self, actor_plan_period_id: UUID, comb_loc_poss_id: UUID):

        self.actor_plan_period_id = actor_plan_period_id
        self.comb_loc_poss_id = comb_loc_poss_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)

    def undo(self):
        db_services.ActorPlanPeriod.put_in_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)

    def redo(self):
        db_services.ActorPlanPeriod.remove_comb_loc_possible(self.actor_plan_period_id, self.comb_loc_poss_id)


class PutInActorLocationPref(Command):
    def __init__(self, actor_plan_period_id: UUID, actor_loc_pref_id: UUID):

        self.actor_plan_period_id = actor_plan_period_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.ActorPlanPeriod.put_in_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)

    def undo(self):
        db_services.ActorPlanPeriod.remove_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)

    def redo(self):
        db_services.ActorPlanPeriod.put_in_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)


class RemoveActorLocationPref(Command):
    def __init__(self, actor_plan_period_id: UUID, actor_loc_pref_id: UUID):

        self.actor_plan_period_id = actor_plan_period_id
        self.actor_loc_pref_id = actor_loc_pref_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)

    def undo(self):
        db_services.ActorPlanPeriod.put_in_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)

    def redo(self):
        db_services.ActorPlanPeriod.remove_location_pref(self.actor_plan_period_id, self.actor_loc_pref_id)


class PutInActorPartnerLocationPref(Command):
    def __init__(self, actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID):

        self.actor_plan_period_id = actor_plan_period_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.ActorPlanPeriod.put_in_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)

    def undo(self):
        db_services.ActorPlanPeriod.remove_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)

    def redo(self):
        db_services.ActorPlanPeriod.put_in_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)


class RemoveActorPartnerLocationPref(Command):
    def __init__(self, actor_plan_period_id: UUID, actor_partner_loc_pref_id: UUID):

        self.actor_plan_period_id = actor_plan_period_id
        self.actor_partner_loc_pref_id = actor_partner_loc_pref_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)

    def undo(self):
        db_services.ActorPlanPeriod.put_in_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)

    def redo(self):
        db_services.ActorPlanPeriod.remove_partner_location_pref(self.actor_plan_period_id,
                                                                 self.actor_partner_loc_pref_id)
