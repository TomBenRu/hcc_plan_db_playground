from uuid import UUID

from commands import command_base_classes
from commands.optimizer_commands import pop_out_pop_in_commands
from optimizer.first_radom_cast import generate_initial_plan_period_cast, AppointmentCast, PlanPeriodCast
from optimizer.fitness_avaluation import fitness_of_plan_period_cast


def generate_initial_cast(plan_period_id: UUID) -> PlanPeriodCast:
    return generate_initial_plan_period_cast(plan_period_id)


def switch_avail_days(plan_period_cast: PlanPeriodCast, nr_random_appointments: int,
                      controller: command_base_classes.ContrExecUndoRedo):
    random_date_cast = plan_period_cast.pick_random_date_cast()
    random_appointments = random_date_cast.pick_random_appointments(nr_random_appointments)

    modified_appointments: list[AppointmentCast] = []

    for appointment in random_appointments:
        try:
            avail_day_to_pop = appointment.pick_random_avail_day()
            controller.execute(pop_out_pop_in_commands.PopOutAvailDay(plan_period_cast, appointment, avail_day_to_pop))
            modified_appointments.append(appointment)
        except IndexError as e:
            pass
    for appointment in modified_appointments:
        avail_day_to_put_in = random_date_cast.pick_random_avail_day()
        controller.execute(pop_out_pop_in_commands.PutInAvailDay(plan_period_cast, appointment, avail_day_to_put_in))


def optimize_plan_period_cast(plan_period_cast: PlanPeriodCast):
    best_fitness = 1000
    nr_iterations = 0
    while True:
        controller = command_base_classes.ContrExecUndoRedo()
        fitness_old = fitness_of_plan_period_cast(initial_cast)

        switch_avail_days(initial_cast, NR_RANDOM_APPOINTMENTS, controller)

        nr_iterations += 1

        fitness_new = fitness_of_plan_period_cast(initial_cast)
        if fitness_new > fitness_old:
            controller.undo_all()

        if not nr_iterations % 10000:
            if (best_curr_fitness := min(fitness_new, fitness_old)) >= best_fitness:
                print(initial_cast)
                print(f'{best_fitness=}')
                print(f'nr of switches: {nr_iterations}')
                break
            else:
                best_fitness = best_curr_fitness
                print(f'{nr_iterations=}, {best_fitness=}')


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0923404BCA2A47579ADE85188CF4EA7F')
    NR_RANDOM_APPOINTMENTS = 2
    initial_cast = generate_initial_cast(PLAN_PERIOD_ID)

    optimize_plan_period_cast(initial_cast)
