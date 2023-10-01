from uuid import UUID

from database import db_services, schemas
from optimizer import optimizers
from optimizer.cast_classes import EventGroupCast, PlanPeriodCast
from optimizer.signal_handling import handler_event_for_plan_period_cast


class Optimizer:
    def __init__(self, plan_period_id: UUID, nr_random_appointment_switches: int):
        self.plan_period_id = plan_period_id
        self.nr_random_appointment_switches = nr_random_appointment_switches

        self.plan_period_cast: PlanPeriodCast = PlanPeriodCast(plan_period_id)

    def optimize_plan_period_cast(self):

        location_plan_periods = db_services.PlanPeriod.get(self.plan_period_id).location_plan_periods
        main_event_groups = [db_services.EventGroup.get_master_from__location_plan_period(lpp.id)
                             for lpp in location_plan_periods]
        initial_main_event_group_casts = [EventGroupCast(evg, None, 0, True) for evg in main_event_groups]
        for egc in initial_main_event_group_casts:
            egc.initialize_first_cast()

        self.plan_period_cast.calculate_initial_casts()

        optimizer_time_of_day_cast = optimizers.TimeOfDaysOptimizer(self.plan_period_cast,
                                                                    self.nr_random_appointment_switches)
        optimizer_time_of_day_cast.optimize()
        self.print_event_group_casts(initial_main_event_group_casts)

    def print_event_group_casts(self, main_event_group_casts: list[EventGroupCast]):
        all_event_group_casts: list[EventGroupCast] = []

        def find_recursive(event_group_cast: EventGroupCast):
            all_event_group_casts.append(event_group_cast)
            for child in event_group_cast.active_groups:
                find_recursive(child)

        for evg in main_event_group_casts:
            find_recursive(evg)
        for evg in (all_event_group_casts):
            print(evg.level, end=', ')


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    NR_RANDOM_APPOINTMENTS = 2

    optimizer = Optimizer(PLAN_PERIOD_ID,NR_RANDOM_APPOINTMENTS)
    optimizer.optimize_plan_period_cast()
