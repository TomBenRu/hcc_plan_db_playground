import collections
import re
from itertools import permutations, combinations
from uuid import UUID

import numpy as np
from line_profiler_pycharm import profile

from database import schemas, db_services
from optimizer import score_factor_tables, score_factors
from optimizer.first_radom_cast import PlanPeriodCast, AppointmentCast


def score_factor_translation(score: float, score_factor_table: dict[int, int]) -> float:
    original_scores = np.array(list(score_factor_table.keys()))
    translate_scores = np.array(list(score_factor_table.values()))

    return np.interp(score, original_scores, translate_scores)


def appointments_from__plan_period_cast(plan_period_cast: PlanPeriodCast) -> list[AppointmentCast]:
    appointments = [appointment
                    for time_of_day_cast in plan_period_cast.time_of_day_casts.values()
                    for appointment in time_of_day_cast.appointments]
    return appointments


def fitness_of_plan_period_cast__time_of_day_cast(
        plan_period_cast: PlanPeriodCast, plan_period: schemas.PlanPeriodShow,
        potential_assignments_of_actors: dict[UUID, int]) -> tuple[float, dict[str, int]]:

    appointments = appointments_from__plan_period_cast(plan_period_cast)

    errors: dict[str, int] = {
        'nones': 0,
        'duplications': 0,
        'partner_location_pref': 0,
        'location_prefs': 0,
        'standard_deviation': 0,
        'fixed_cast': 0
    }

    requested_assignments: dict[UUID: int] = {app.person.id: app.requested_assignments
                                              for app in plan_period.actor_plan_periods}
    current_assignments: dict[UUID, int] = {person_id: 0 for person_id in requested_assignments}

    for appointment in appointments:
        errors['nones'] += appointment.avail_days.count(None)
        duplication_counter = collections.Counter(
            (avd.actor_plan_period.person.id for avd in appointment.avail_days if avd is not None))
        errors['duplications'] += (sum(count for count in duplication_counter.values() if count > 1)
                                   * score_factors.duplication)
        errors['partner_location_pref'] += partner_location_pref(appointment)
        errors['location_prefs'] += location_prefs(appointment)

        for avail_day in appointment.avail_days:
            if avail_day is None:
                continue
            person_id = avail_day.actor_plan_period.person.id
            current_assignments[person_id] += 1
    requested_assignments = generate_adjusted_requested_assignments(
        plan_period_cast, errors['nones'], requested_assignments, potential_assignments_of_actors)
    errors['standard_deviation'] = standard_deviation_score(requested_assignments, current_assignments)
    errors['fixed_cast'] += fixed_cast_score(plan_period_cast)

    return sum(errors.values()), errors


def location_prefs(appointment: AppointmentCast) -> float:
    location_of_work_id = appointment.event.location_plan_period.location_of_work.id

    score_result = 0

    for avail_day in appointment.avail_days:
        if not avail_day:
            continue
        location_pref = next((alp.score for alp in avail_day.actor_location_prefs_defaults
                              if alp.location_of_work.id == location_of_work_id and not alp.prep_delete), 1)
        score_result += score_factor_translation(location_pref, score_factor_tables.actor_location_prefs)

    return score_result


def partner_location_pref(appointment: AppointmentCast) -> float:
    """Berechnung: ((score_1-1)/(nr_actors-1)+1)*(score_2-1)/(nr_actors-1)+1)*Wertungsfaktor = score_result
    für den entsprechenden Actor.
    Dies wird für jede Actor-Partner-Kombi durchgeführt und anschließend summiert."""

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

        score_results.append(score_factor_translation(score_partners, score_factor_tables.actor_partner_location_prefs))

    return sum(score_results) / len(score_results) if score_results else 0


def fixed_cast_score(plan_period_cast: PlanPeriodCast) -> float:
    # fixme: gilt bislang nur für unterste Ebene
    def replace_uuid_except_nth(fixed_cast_text):
        pattern = r'UUID\(.*?\)'
        occurrences = len(re.findall(pattern, fixed_cast_text))

        for i in range(1, occurrences + 1):
            count = [0]

            def replacer(match):
                count[0] += 1
                return match.group(0) if count[0] == i else 'None'

            replaced_text = re.sub(pattern, replacer, fixed_cast_text)
            yield replaced_text

    appointments = appointments_from__plan_period_cast(plan_period_cast)
    score_result = 0
    for appointment in appointments:
        fixed_cast = appointment.event.cast_group.fixed_cast
        if fixed_cast:
            person_ids: list[UUID | None] = [avd.actor_plan_period.person.id if avd else None
                                             for avd in appointment.avail_days]
            conditions_met = eval(fixed_cast, {'team': person_ids, 'UUID': UUID})
            if not conditions_met:
                for modified_fixed_cast in replace_uuid_except_nth(fixed_cast):
                    # print(f'{modified_fixed_cast=}')
                    modified_conditions_met = eval(modified_fixed_cast, {'team': person_ids, 'UUID': UUID})
                    score_result += score_factors.fixed_cast if not modified_conditions_met else 0



            # score_result += score_factors.fixed_cast if not conditions_met else 0

    return score_result


def potential_assignments_of_persons(plan_period_cast: PlanPeriodCast, plan_period_id: UUID) -> dict[UUID, int]:
    appointments = appointments_from__plan_period_cast(plan_period_cast)

    potential_assignments = collections.defaultdict(int)
    for appointment in appointments:
        potential_avail_days = db_services.AvailDay.get_all_from__plan_period__date__time_of_day__location_prefs(
            plan_period_id, appointment.event.date, appointment.event.time_of_day.time_of_day_enum.time_index,
            {appointment.event.location_plan_period.location_of_work.id})
        for avail_day in potential_avail_days:
            potential_assignments[avail_day.actor_plan_period.person.id] += 1
    return potential_assignments


def generate_adjusted_requested_assignments(
        plan_period_cast: PlanPeriodCast, unoccupied: int, requested_assignments: dict[UUID, int],
        potential_assignments_of_actors: dict[UUID, int]) -> dict[UUID, float]:
    requested_assignments_adjusted = collections.defaultdict(int)
    appointments = [appointment
                    for time_of_day_cast in plan_period_cast.time_of_day_casts.values()
                    for appointment in time_of_day_cast.appointments]
    sum_taken_assignments: int = sum(appointment.event.cast_group.nr_actors for appointment in appointments) - unoccupied

    for person_id, potential_nr in requested_assignments.items():
        requested_assignments_adjusted[person_id] = min(potential_nr, potential_assignments_of_actors.get(person_id, 0))

    requested_assignments_new: dict[UUID: int] = {}
    avail_assignments: int = sum_taken_assignments
    while True:
        mean_nr_assignments: float = avail_assignments / len(requested_assignments_adjusted)
        requested_greater_than_mean: dict[UUID: int] = {}
        requested_smaller_than_mean: dict[UUID: int] = {}
        for p_id, requested in requested_assignments_adjusted.items():
            if requested >= mean_nr_assignments:
                requested_greater_than_mean[p_id] = requested
            else:
                requested_smaller_than_mean[p_id] = requested

        if not requested_smaller_than_mean:
            requested_assignments_new.update({p_id: avail_assignments / len(requested_greater_than_mean)
                                              for p_id in requested_greater_than_mean})
            break
        else:
            requested_assignments_new.update(requested_smaller_than_mean)
            avail_assignments -= sum(requested_smaller_than_mean.values())
            requested_assignments_adjusted = requested_greater_than_mean.copy()
            if not requested_assignments_adjusted:
                break
    return requested_assignments_new


def standard_deviation_score(requested_assignments: dict[UUID: int], current_assignments: dict[UUID, int]) -> int:
    relative_deviations = [
        (requested - current) / (requested if requested else 0.001)
        * score_factor_tables.requested_assignments.get(requested, 1)
        for requested, current in zip(requested_assignments.values(), current_assignments.values())
    ]
    standard_deviation = np.std(relative_deviations) * score_factors.standard_deviation_factor

    return standard_deviation
