import pickle
from uuid import UUID

from database import db_services, schemas
from optimizer import optimizers
from optimizer.base_cast_classes import BaseEventGroupCast, BasePlanPeriodCast
from optimizer.cast_classes import EventGroupCast, PlanPeriodCast, event_group_cast_levels
from optimizer.signal_handling import handler_event_for_plan_period_cast


class Optimizer:
    def __init__(self, plan_period_id: UUID, nr_random_appointment_switches: int):
        self.plan_period_id = plan_period_id
        self.nr_random_appointment_switches = nr_random_appointment_switches

        self.plan_period_cast: PlanPeriodCast = PlanPeriodCast(plan_period_id)

        self.location_plan_periods = db_services.PlanPeriod.get(self.plan_period_id).location_plan_periods
        self.main_event_groups = [db_services.EventGroup.get_master_from__location_plan_period(lpp.id)
                                  for lpp in self.location_plan_periods]
        self.initial_main_event_group_casts: list[EventGroupCast] = []

        self.best_group_cast_state: bytes | None = None
        self.best_plan_period_cast_fitness = float('inf')
        self.best_plan_period_cast_state: bytes | None = None

    def optimize_plan_period_cast(self):
        self.generate_event_group_casts()
        self.plan_period_cast.calculate_initial_casts()

        optimizer_time_of_day_cast = optimizers.TimeOfDayCastOptimizer(self.plan_period_cast,
                                                                       self.nr_random_appointment_switches)
        curr_fitness_of_plan_period_cast = optimizer_time_of_day_cast.optimize()
        if curr_fitness_of_plan_period_cast < self.best_plan_period_cast_fitness:
            self.best_plan_period_cast_fitness = curr_fitness_of_plan_period_cast
            self.pickle_current_states_to_best()

        self.print_event_group_cast_levels()

    def generate_event_group_casts(self):
        self.initial_main_event_group_casts = [EventGroupCast(evg, None, 0, True) for evg in self.main_event_groups]
        for egc in self.initial_main_event_group_casts:
            egc.initialize_first_cast()

    def pickle_current_states_to_best(self):
        self.best_group_cast_state = pickle.dumps(self.initial_main_event_group_casts)
        self.best_plan_period_cast_state = pickle.dumps(self.plan_period_cast)

    def load_best_group_cast_state(self) -> tuple[list[BaseEventGroupCast], BasePlanPeriodCast]:
        group_state: list[BaseEventGroupCast] = pickle.loads(self.best_group_cast_state)
        plan_period_state: BasePlanPeriodCast = pickle.loads(self.best_plan_period_cast_state)
        return group_state, plan_period_state

    def print_event_group_cast_levels(self):
        print('#####################################################################################')
        print([f'{level}: {[f"(childs: {len(egc.child_groups) + len(egc.active_groups)}, nr_event_groups: {egc.event_group.nr_event_groups})" for egc in egcs]}'
               for level, egcs in event_group_cast_levels.items()])
        print('#####################################################################################')


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    NR_RANDOM_APPOINTMENTS = 2

    optimizer = Optimizer(PLAN_PERIOD_ID,NR_RANDOM_APPOINTMENTS)
    optimizer.optimize_plan_period_cast()
