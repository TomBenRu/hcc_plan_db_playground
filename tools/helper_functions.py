import datetime
from collections import defaultdict
from typing import Literal
from uuid import UUID

from PySide6.QtCore import QDate

from line_profiler_pycharm import profile

from database import db_services, schemas


def backtranslate_eval_str(fixed_cast: str, str_for_team: str = 'team'):
    form = []
    eval_str = fixed_cast
    if not eval_str:
        return
    e_s = eval_str.replace('and', ',"and",').replace('or', ',"or",').replace(f'in {str_for_team}', '')
    e_s = eval(e_s)
    if type(e_s) != tuple:
        e_s = (e_s,)
    for element in e_s:
        if type(element) == tuple:
            break
    else:
        e_s = [e_s]
    for val in e_s:
        if type(val) in [int, UUID]:
            form.append([val])
        elif type(val) == str:
            form.append(val)
        else:
            form.append(list(val))
    return form


def generate_fixed_cast_clear_text(fixed_cast: str | None):
    replace_map = {'and': 'und', 'or': 'oder'}

    def generate_recursive(item_list: list):
        clear_list = []
        for item in item_list:
            if isinstance(item, str):
                clear_list.append(replace_map[item])
            elif isinstance(item, UUID):
                person = db_services.Person.get(item)
                clear_list.append(f'{person.f_name} {person.l_name}')
            else:
                clear_list.append(str(generate_recursive(item)))
        return clear_list[0] if len(clear_list) == 1 else '(' + ' '.join(clear_list) + ')'
    item = backtranslate_eval_str(fixed_cast)
    clear_text = generate_recursive(item or [])
    if clear_text.startswith('('):
        clear_text = clear_text[1:]
    if clear_text.endswith(')'):
        clear_text = clear_text[:-1]

    return clear_text


def get_appointments_of_actors_from_plan(plan: schemas.PlanShow) -> dict[str, list[schemas.Appointment]]:
    pp: schemas.PlanPeriodShow
    name_appointments: defaultdict[str, list[schemas.Appointment]] = defaultdict(list)
    for appointment in plan.appointments:
        for avail_day in appointment.avail_days:
            name_appointments[avail_day.actor_plan_period.person.full_name].append(appointment)
        for name in appointment.guests:
            name_appointments[name].append(appointment)
    for appointments in name_appointments.values():
        appointments.sort(key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index))

    return {name: name_appointments[name] for name in sorted(name_appointments.keys())}


def get_appointments_of_all_actors_from_plan(
        plan: schemas.PlanShow) -> dict[str, tuple[schemas.ActorPlanPeriod | None, list[schemas.Appointment]]]:
    actor_plan_periods = db_services.ActorPlanPeriod.get_all_from__plan_period(plan.plan_period.id)
    actor_ids_between_dates = db_services.TeamActorAssign.get_all_actor_ids_between_dates(
        plan.plan_period.team.id, plan.plan_period.start, plan.plan_period.end)
    result: dict[str, tuple[schemas.ActorPlanPeriod | None, list[schemas.Appointment]]] = {
        app.person.full_name: (app, []) for app in actor_plan_periods
        if app.person.id in actor_ids_between_dates
    }
    for appointment in plan.appointments:
        for avail_day in appointment.avail_days:
            result[avail_day.actor_plan_period.person.full_name][1].append(appointment)
        for name in appointment.guests:
            if not result.get(name):
                result[name] = (None, [])
            result[name][1].append(appointment)
    for _, appointments in result.values():
        appointments.sort(key=lambda x: (x.event.date, x.event.time_of_day.time_of_day_enum.time_index))

    return {name: result[name] for name in sorted(result.keys())}


def n_th_weekday_of_period(start: datetime.date, end: datetime.date, weekday: int, n: int) -> datetime.date | None:
    """
    Bestimm den n-ten Wochentag in einem Zeitraum.
    weekdays: (0 = Montag, ..., 6 = Sonntag)
    """
    if n < 1:
        return None
    # Berechnung des ersten Wochentags
    delta_days = (weekday - start.weekday()) % 7
    date_of_first_weekday = start + datetime.timedelta(days=delta_days)
    # Berechnung des n-ten Wochentags
    if (date_of_n_th_weekday := (date_of_first_weekday + datetime.timedelta(days=7 * (n - 1)))) > end:
        return None
    return date_of_n_th_weekday


def datetime_date_to_qdate(date: datetime.date) -> QDate:
    return QDate(date.year, date.month, date.day)


def date_to_string(date: datetime.date, lang: str) -> str:
    if lang == 'en':
        return date.strftime('%y-%m-%d')
    return date.strftime('%d.%m.%y')


if __name__ == '__main__':
    print(n_th_weekday_of_period(datetime.date(2024, 11, 1),
                                   datetime.date(2024, 11, 30), 4, 1))
