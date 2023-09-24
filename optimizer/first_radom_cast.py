import dataclasses
import datetime
import random
import time
from typing import Literal
from uuid import UUID

from dateutil.relativedelta import relativedelta

from database import db_services, schemas
from database.special_schema_requests import get_persons_of_team_at_date


def get_all_events_from__plan_period(plan_period_id: UUID) -> list[schemas.EventShow]:
    return db_services.Event.get_all_from__plan_period(plan_period_id)


@dataclasses.dataclass
class TimeSpan:
    start: datetime.datetime
    span: relativedelta

    def __str__(self):
        return f'{self.start:%d.-%H:%M}, {self.span.hours:02}:{self.span.minutes:02}'


class AvailDayParts:
    def __init__(self, avail_day: schemas.AvailDayShow):
        self.avail_day = avail_day
        self.time_spans: list[TimeSpan] = []

        self.initialize_time_spans()

    def initialize_time_spans(self):
        time_start = datetime.datetime.combine(self.avail_day.date, self.avail_day.time_of_day.start)
        time_end = datetime.datetime.combine(self.avail_day.date, self.avail_day.time_of_day.end)
        if self.avail_day.time_of_day.start > self.avail_day.time_of_day.end:
            time_end += datetime.timedelta(days=1)
        self.time_spans.append(TimeSpan(time_start, relativedelta(dt1=time_end, dt2=time_start)))

    def __str__(self):
        return ', '.join([str(ts) for ts in self.time_spans])


@dataclasses.dataclass
class AppointmentCast:
    event: schemas.EventShow
    avail_days: list[schemas.AvailDayShow | None] = dataclasses.field(default_factory=list)

    def add_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.append(avail_day)

    def remove_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.remove(avail_day)

    def pick_random_avail_day(self) -> schemas.AvailDayShow | None:
        return random.choice(self.avail_days)

    def add_avail_day_first_cast(self, avail_day: schemas.AvailDayShow) -> Literal['filled', 'same person', 'full']:
        if len(self.avail_days) < self.event.cast_group.nr_actors:
            person_id = avail_day.actor_plan_period.person.id if avail_day else None
            if person_id not in {avd.actor_plan_period.person.id for avd in self.avail_days if avd}:
                self.avail_days.append(avail_day)
                return 'filled'
            else:
                return 'same person'
        return 'full'

    def __str__(self):
        return (f'{self.event.date:%d.%m.} ({self.event.time_of_day.name}): '
                f'{self.event.location_plan_period.location_of_work.name}, '
                f'Cast ({self.event.cast_group.nr_actors}): '
                f'{", ".join(avd.actor_plan_period.person.f_name if avd else "unbesetzt" for avd in self.avail_days)}')


class DateCast:
    def __init__(self, date: datetime.date, avail_days: list[schemas.AvailDayShow]):
        self.date = date
        self.appointments: list[AppointmentCast] = []
        self.avail_days: list[schemas.AvailDayShow | None] = avail_days

    def add_appointment(self, event: schemas.EventShow):
        self.appointments.append(AppointmentCast(event))

    def add_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.append(avail_day)

    def remove_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.remove(avail_day)
    
    def pick_random_appointments(self, nr_appointments: int) -> list[AppointmentCast]:
        return [random.choice(self.appointments) for _ in range(nr_appointments)]

    def pick_random_avail_day(self) -> schemas.AvailDayShow | None:
        return random.choice(self.avail_days)

    def initialize_first_cast(self):  # not_sure: kann weggelassen werden
        appointments_indexes = list(range(len(self.appointments)))
        avail_days_indexes = list(range(len(self.avail_days)))
        random.shuffle(avail_days_indexes)

        avd_to_remove_indexes = []
        while appointments_indexes and avail_days_indexes:
            avd_idx = avail_days_indexes.pop()
            appointm_idx = random.choice(appointments_indexes)
            result = self.appointments[appointm_idx].add_avail_day_first_cast(self.avail_days[avd_idx])
            if result == 'full':
                avail_days_indexes.append(avd_idx)
                appointments_indexes.remove(appointm_idx)
            elif result == 'same person':
                avail_days_indexes.append(avd_idx)
            else:
                avd_to_remove_indexes.append(avd_idx)
        self.avail_days = [avd for idx, avd in enumerate(self.avail_days) if idx not in avd_to_remove_indexes]


    def __str__(self):
        return '\n'.join([str(appointment) for appointment in self.appointments])


@dataclasses.dataclass
class PlanPeriodCast:
    plan_period_id: UUID
    date_casts: dict[datetime.date, 'DateCast'] = dataclasses.field(default_factory=dict)

    def calculate_date_casts(self):
        events = get_all_events_from__plan_period(self.plan_period_id)
        for event in events:
            if not self.date_casts.get(event.date):
                avail_days_at_date = db_services.AvailDay.get_all_from__plan_period_date(
                    self.plan_period_id, event.date)
                avail_days_at_date += [None] * sum(e.cast_group.nr_actors for e in events)
                self.date_casts[event.date] = DateCast(event.date, avail_days_at_date)
            self.date_casts[event.date].add_appointment(event)

    def pick_random_date_cast(self) -> DateCast:
        return random.choice(list(self.date_casts.values()))
    
    def calculate_initial_casts(self):  # not_sure: kann weggelassen werden
        for date_cast in self.date_casts.values():
            date_cast.initialize_first_cast()

    def __str__(self):
        return '\n----------------\n'.join([str(date_cast) for date_cast in self.date_casts.values()])


def generate_initial_plan_period_cast(plan_period_id: UUID) -> PlanPeriodCast:
    plan_period_cast = PlanPeriodCast(plan_period_id)
    plan_period_cast.calculate_date_casts()
    plan_period_cast.calculate_initial_casts()  # not_sure: kann weggelassen werden

    return plan_period_cast


if __name__ == '__main__':
    initial_cast = generate_initial_plan_period_cast(UUID('0923404BCA2A47579ADE85188CF4EA7F'))

    print(initial_cast)


# todo: Controller und Commands für Auspoppen und Einsetzten von Personen in Appointments im DateCast
