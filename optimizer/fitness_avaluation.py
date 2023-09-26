import collections
from itertools import permutations, combinations

import numpy as np
from line_profiler_pycharm import profile

from database import schemas
from optimizer import score_factor_tables
from optimizer.first_radom_cast import PlanPeriodCast, AppointmentCast


def fitness_of_plan_period_cast__time_of_day_cast(plan_period_cast: PlanPeriodCast) -> float:
    errors: dict[str, int] = {'nones': 0, 'duplications': 0, 'partner_location_pref': 0, 'location_prefs': 0}
    for time_of_day_cast in plan_period_cast.time_of_day_casts.values():
        for appointment in time_of_day_cast.appointments:
            errors['nones'] += appointment.avail_days.count(None)
            duplication_counter = collections.Counter(
                (avd.actor_plan_period.person.id for avd in appointment.avail_days if avd is not None))
            errors['duplications'] += sum(count for count in duplication_counter.values() if count > 1)
            errors['partner_location_pref'] += partner_location_pref(appointment)
    return sum(errors.values())


def location_prefs(appointment: AppointmentCast) -> float:
    ...


def partner_location_pref(appointment: AppointmentCast) -> float:
    """Berechnung: ((score_1-1)/(nr_actors-1)+1)*(score_2-1)/(nr_actors-1)+1)*Wertungsfaktor = score_result
    für den entsprechenden Actor.
    Dies wird für jede Actor-Partner-Kombi durchgeführt und anschließend summiert."""

    def score_factor_translation(score: float) -> float:
        score_factors = score_factor_tables.actor_partner_location_pref
        original_scores = np.array(list(score_factors.keys()))
        translate_scores = np.array(list(score_factors.values()))

        return np.interp(score, original_scores, translate_scores)

    location_of_work_id = appointment.event.location_plan_period.location_of_work.id
    nr_of_avail_days = len(appointment.avail_days)

    score_results = []

    for avd_1, avd_2 in combinations(appointment.avail_days, 2):
        if not (avd_1 and avd_2):
            continue
        avd_1: schemas.AvailDayShow
        avd_2: schemas.AvailDayShow

        person_1_id = avd_1.actor_plan_period.person.id
        person_2_id = avd_2.actor_plan_period.person.id

        person_1_score = next((apl.score for apl in avd_1.actor_partner_location_prefs_defaults
                               if apl.location_of_work.id == location_of_work_id
                               and apl.partner.id == person_2_id
                               and not apl.prep_delete), 1)
        person_2_score = next((apl.score for apl in avd_2.actor_partner_location_prefs_defaults
                               if apl.location_of_work.id == location_of_work_id
                               and apl.partner.id == person_1_id
                               and not apl.prep_delete), 1)

        score_1 = (person_1_score - 1) / (nr_of_avail_days - 1) + 1
        score_2 = (person_2_score - 1) / (nr_of_avail_days - 1) + 1

        score_partners = score_1 * score_2

        score_results.append(score_factor_translation(score_partners))

    return sum(score_results) / len(score_results) if score_results else 0


