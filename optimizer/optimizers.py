from uuid import UUID

from commands import command_base_classes
from commands.optimizer_commands import pop_out_pop_in_commands
from database import db_services
from optimizer.base_cast_classes import BaseAppointmentCast
from optimizer.cast_classes import PlanPeriodCast
from optimizer.fitness_avaluation import potential_assignments_of_persons, fitness_of_plan_period_cast__time_of_day_cast


class TimeOfDayCastOptimizer:
    def __init__(self, plan_period_cast: PlanPeriodCast, nr_random_appointments: int):
        self.plan_period_cast = plan_period_cast
        self.nr_random_appointments = nr_random_appointments
        self.plan_period = db_services.PlanPeriod.get(self.plan_period_cast.plan_period_id)

    def optimize(self) -> float:
        potential_assignments_of_actors = potential_assignments_of_persons(self.plan_period_cast)
        all_persons_from__plan_period: list[UUID] = [  # wird für fixed_cast_score benötigt
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

            self.switch_avail_days__time_of_day_cast(controller)

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

        return best_fitness

    def switch_avail_days__time_of_day_cast(self, controller: command_base_classes.ContrExecUndoRedo):
        # Weil es sein kann, dass - wegen event_groups - Tageszeiten keine Appointments besitzen:
        random_appointments = []
        while not random_appointments:
            random_time_of_day_cast = self.plan_period_cast.pick_random_time_of_day_cast()
            random_appointments = random_time_of_day_cast.pick_random_appointments(self.nr_random_appointments)

        modified_appointments: list[BaseAppointmentCast] = []

        for appointment in random_appointments:
            try:
                avail_day_to_pop = appointment.pick_random_avail_day()
                controller.execute(pop_out_pop_in_commands.TimeOfDayCastPopOutAvailDay(
                    self.plan_period_cast, appointment, avail_day_to_pop))
                modified_appointments.append(appointment)
            except IndexError as e:
                pass
        for appointment in modified_appointments:
            avail_day_to_put_in = random_time_of_day_cast.pick_random_avail_day()
            controller.execute(pop_out_pop_in_commands.TimeOfDayCastPutInAvailDay(
                self.plan_period_cast, appointment, avail_day_to_put_in))
