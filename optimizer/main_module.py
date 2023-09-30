from uuid import UUID

from optimizer import optimizers
from optimizer.first_radom_cast import generate_initial_plan_period_cast


def optimize_plan_period_cast(plan_period_id: UUID, nr_random_appointments: int):
    initial_plan_period_cast = generate_initial_plan_period_cast(plan_period_id)

    optimizer_time_of_day_cast = optimizers.TimeOfDays(initial_plan_period_cast, nr_random_appointments)
    optimizer_time_of_day_cast.optimize()


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    NR_RANDOM_APPOINTMENTS = 2

    optimize_plan_period_cast(PLAN_PERIOD_ID, NR_RANDOM_APPOINTMENTS)
