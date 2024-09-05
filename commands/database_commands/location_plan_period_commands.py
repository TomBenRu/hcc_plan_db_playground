import datetime
from uuid import UUID

from database import db_services, schemas
from commands.command_base_classes import Command


class CreateLocationPlanPeriodsFromDate(Command):
    def __init__(self, start_date: datetime.date, location_id: UUID, team_id: UUID):
        self.start_date = start_date
        self.location_id = location_id
        self.team_id = team_id
        self.location_plan_periods: list[schemas.LocationPlanPeriodShow] = []
        self.master_event_groups = []

    def get_plan_periods(self) -> list[schemas.PlanPeriodShow]:
        return [pp for pp in db_services.PlanPeriod.get_all_from__team(self.team_id)
                if pp.end > self.start_date]

    def execute(self):
        for pp in self.get_plan_periods():
            if self.location_id in {lpp.location_of_work.id for lpp in pp.location_plan_periods}:
                continue
            self.location_plan_periods.append(db_services.LocationPlanPeriod.create(pp.id, self.location_id))

    def undo(self):
        for lpp in self.location_plan_periods:
            db_services.LocationPlanPeriod.delete(lpp.id)

    def redo(self):
        for lpp in self.location_plan_periods:
            db_services.LocationPlanPeriod.create(lpp.plan_period.id, lpp.location_of_work.id, lpp.id)


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


class UpdateFixedCast(Command):
    def __init__(self, location_plan_period_id: UUID, fixed_cast: str | None):
        self.location_plan_period_id = location_plan_period_id
        self.fixed_cast = fixed_cast
        self.fixed_cast_old = None

    def execute(self):
        self.fixed_cast_old = db_services.LocationPlanPeriod.get(self.location_plan_period_id).fixed_cast
        db_services.LocationPlanPeriod.update_fixed_cast(self.location_plan_period_id, self.fixed_cast)

    def undo(self):
        db_services.LocationPlanPeriod.update_fixed_cast(self.location_plan_period_id, self.fixed_cast_old)

    def redo(self):
        db_services.LocationPlanPeriod.update_fixed_cast(self.location_plan_period_id, self.fixed_cast)
