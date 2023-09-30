import time
from uuid import UUID

from line_profiler_pycharm import profile

from commands import command_base_classes
from commands.optimizer_commands import pop_out_pop_in_commands
from database import db_services, schemas
from optimizer.first_radom_cast import generate_initial_plan_period_cast, AppointmentCast, PlanPeriodCast
from optimizer.fitness_avaluation import fitness_of_plan_period_cast__time_of_day_cast, potential_assignments_of_persons


def generate_initial_cast(plan_period_id: UUID) -> PlanPeriodCast:
    return generate_initial_plan_period_cast(plan_period_id)


def switch_avail_days__time_of_day_cast(plan_period_cast: PlanPeriodCast, nr_random_appointments: int,
                                        controller: command_base_classes.ContrExecUndoRedo):
    random_time_of_day_cast = plan_period_cast.pick_random_time_of_day_cast()
    random_appointments = random_time_of_day_cast.pick_random_appointments(nr_random_appointments)

    modified_appointments: list[AppointmentCast] = []

    for appointment in random_appointments:
        try:
            avail_day_to_pop = appointment.pick_random_avail_day()
            controller.execute(pop_out_pop_in_commands.TimeOfDayCastPopOutAvailDay(
                plan_period_cast, appointment, avail_day_to_pop))
            modified_appointments.append(appointment)
        except IndexError as e:
            pass
    for appointment in modified_appointments:
        avail_day_to_put_in = random_time_of_day_cast.pick_random_avail_day()
        controller.execute(pop_out_pop_in_commands.TimeOfDayCastPutInAvailDay(
            plan_period_cast, appointment, avail_day_to_put_in))


@profile
def optimize_plan_period_cast(plan_period_cast: PlanPeriodCast, nr_random_appointments: int):
    plan_period = db_services.PlanPeriod.get(plan_period_cast.plan_period_id)
    potential_assignments_of_actors = potential_assignments_of_persons(plan_period_cast,
                                                                       plan_period_cast.plan_period_id)
    all_persons_from__plan_period: list[UUID] = [
        p.id for p in db_services.Person.get_all_from__plan_period(plan_period_cast.plan_period_id)
    ]

    best_fitness, best_errors = float('inf'), {}
    nr_iterations = 0
    curr_fitness, curr_errors = fitness_of_plan_period_cast__time_of_day_cast(
        plan_period_cast, plan_period, potential_assignments_of_actors,
        all_persons_from__plan_period
    )
    while True:
        controller = command_base_classes.ContrExecUndoRedo()

        switch_avail_days__time_of_day_cast(plan_period_cast, nr_random_appointments, controller)

        nr_iterations += 1

        fitness_new, new_errors = fitness_of_plan_period_cast__time_of_day_cast(
            plan_period_cast, plan_period, potential_assignments_of_actors,
            all_persons_from__plan_period
        )
        if fitness_new > curr_fitness:
            controller.undo_all()
        else:
            curr_fitness, curr_errors = fitness_new, new_errors

        if not nr_iterations % 100:
            print(f'{nr_iterations=}, {curr_fitness=}')
            print(f'{curr_errors=}')

        if not nr_iterations % 2000:
            if curr_fitness >= best_fitness:
                print(plan_period_cast)
                print(f'{best_fitness=}')
                print(f'{best_errors=}')
                print(f'nr of switches: {nr_iterations=}')
                break
            else:
                best_fitness, best_errors = curr_fitness, curr_errors
                print(f'{nr_iterations=}, {best_fitness=}')
                print(f'{best_errors=}')


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    NR_RANDOM_APPOINTMENTS = 2
    initial_cast = generate_initial_cast(PLAN_PERIOD_ID)

    plan_period = db_services.PlanPeriod.get(PLAN_PERIOD_ID)

    optimize_plan_period_cast(initial_cast, NR_RANDOM_APPOINTMENTS)
