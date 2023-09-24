import collections

from optimizer.first_radom_cast import PlanPeriodCast


def fitness_of_plan_period_cast(plan_period_cast: PlanPeriodCast) -> float:
    errors: dict[str, int] = {'nones': 0, 'duplications': 0}
    for date_cast in plan_period_cast.date_casts.values():
        for appointment in date_cast.appointments:
            errors['nones'] += appointment.avail_days.count(None)
            duplication_counter = collections.Counter(
                (avd.actor_plan_period.person.id for avd in appointment.avail_days if avd is not None))
            errors['duplications'] += sum(count for count in duplication_counter.values() if count > 1)
    return sum(errors.values())
