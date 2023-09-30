from uuid import UUID

from commands import command_base_classes
from database import db_services
from optimizer.first_radom_cast import PlanPeriodCast
from optimizer.fitness_avaluation import potential_assignments_of_persons, fitness_of_plan_period_cast__time_of_day_cast
from optimizer.switchers import switch_avail_days__time_of_day_cast


class TimeOfDays:
    def __init__(self, plan_period_cast: PlanPeriodCast, nr_random_appointments: int):
        self.plan_period_cast = plan_period_cast
        self.nr_random_appointments = nr_random_appointments
        self.plan_period = db_services.PlanPeriod.get(self.plan_period_cast.plan_period_id)

    def optimize(self):
        potential_assignments_of_actors = potential_assignments_of_persons(self.plan_period_cast,
                                                                           self.plan_period_cast.plan_period_id)
        all_persons_from__plan_period: list[UUID] = [
            p.id for p in db_services.Person.get_all_from__plan_period(self.plan_period_cast.plan_period_id)
        ]

        best_fitness, best_errors = float('inf'), {}
        nr_iterations = 0
        curr_fitness, curr_errors = fitness_of_plan_period_cast__time_of_day_cast(
            self.plan_period_cast, self.plan_period, potential_assignments_of_actors,
            all_persons_from__plan_period
        )
        while True:
            controller = command_base_classes.ContrExecUndoRedo()

            switch_avail_days__time_of_day_cast(self.plan_period_cast, self.nr_random_appointments, controller)

            nr_iterations += 1

            fitness_new, new_errors = fitness_of_plan_period_cast__time_of_day_cast(
                self.plan_period_cast, self.plan_period, potential_assignments_of_actors,
                all_persons_from__plan_period
            )
            if fitness_new > curr_fitness:
                controller.undo_all()
            else:
                curr_fitness, curr_errors = fitness_new, new_errors

            if not nr_iterations % 100:
                print(f'{nr_iterations=}, {curr_fitness=}')
                print(f'{curr_errors=}')

            if not nr_iterations % 600:
                if curr_fitness >= best_fitness:
                    print(self.plan_period_cast)
                    print(f'{best_fitness=}')
                    print(f'{best_errors=}')
                    print(f'nr of switches: {nr_iterations=}')
                    break
                else:
                    best_fitness, best_errors = curr_fitness, curr_errors
                    print(f'{nr_iterations=}, {best_fitness=}')
                    print(f'{best_errors=}')