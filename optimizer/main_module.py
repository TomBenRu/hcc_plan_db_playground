from uuid import UUID

from database import db_services, schemas
from optimizer import optimizers
from optimizer.first_radom_cast import generate_initial_plan_period_cast, EventGroupCast
from optimizer.signal_handling import handler_event_for_plan_period_cast

e: schemas.EventShow
handler_event_for_plan_period_cast.signal_new_event.connect(lambda e: print(f'{e.date}, {e.time_of_day.name}, {e.location_plan_period.location_of_work.name}'))


def optimize_plan_period_cast(plan_period_id: UUID, nr_random_appointments: int):
    initial_plan_period_cast = generate_initial_plan_period_cast(plan_period_id)

    location_plan_periods = db_services.PlanPeriod.get(plan_period_id).location_plan_periods
    main_event_groups = [db_services.EventGroup.get_master_from__location_plan_period(lpp.id)
                         for lpp in location_plan_periods]
    main_event_group_casts = [EventGroupCast(evg) for evg in main_event_groups]
    return
    print(f'{main_event_group_casts=}')


    optimizer_time_of_day_cast = optimizers.TimeOfDaysOptimizer(initial_plan_period_cast, nr_random_appointments)
    optimizer_time_of_day_cast.optimize()


if __name__ == '__main__':
    PLAN_PERIOD_ID = UUID('0BD5C3876C4E48D1B84D6F395CD74C65')
    NR_RANDOM_APPOINTMENTS = 2

    optimize_plan_period_cast(PLAN_PERIOD_ID, NR_RANDOM_APPOINTMENTS)
