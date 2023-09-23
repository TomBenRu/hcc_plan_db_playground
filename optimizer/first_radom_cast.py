import dataclasses
import datetime
import random
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


date_casts: dict[datetime.date, 'DateCast'] = {}

@dataclasses.dataclass
class AppointmentCalc:
    event: schemas.EventShow
    avail_days: list[schemas.AvailDayShow] = dataclasses.field(default_factory=list)

    def add_avail_day(self, avail_day: schemas.AvailDayShow) -> bool:
        if len(self.avail_days) < self.event.cast_group.nr_actors:
            self.avail_days.append(avail_day)
            return True
        return False

    def __str__(self):
        return (f'{self.event.date:%d.%m.} ({self.event.time_of_day.name}): '
                f'{self.event.location_plan_period.location_of_work.name}, '
                f'Cast ({self.event.cast_group.nr_actors}): {", ".join(avd.actor_plan_period.person.f_name for avd in self.avail_days)}')


class DateCast:
    def __init__(self, date: datetime.date, avail_days: list[schemas.AvailDayShow]):
        self.date = date
        self.appointments: list[AppointmentCalc] = []
        self.avail_days: list[schemas.AvailDayShow] = avail_days

    def add_appointment(self, event: schemas.EventShow):
        self.appointments.append(AppointmentCalc(event))

    def add_avail_day(self, avail_day: schemas.AvailDayShow):
        self.avail_days.append(avail_day)

    def initialize_cast(self):
        appointments_indexes = list(range(len(self.appointments)))
        avail_days_indexes = list(range(len(self.avail_days)))
        random.shuffle(avail_days_indexes)
        while appointments_indexes and avail_days_indexes:
            avd_idx = avail_days_indexes.pop()
            appointm_idx = random.choice(appointments_indexes)
            if not self.appointments[appointm_idx].add_avail_day(self.avail_days[avd_idx]):
                avail_days_indexes.append(avd_idx)
                appointments_indexes.remove(appointm_idx)


if __name__ == '__main__':
    plan_period_id = UUID('0923404BCA2A47579ADE85188CF4EA7F')

    plan_period = db_services.PlanPeriod.get(plan_period_id)
    events = get_all_events_from__plan_period(plan_period_id)

    for e in events:
        if not date_casts.get(e.date):
            avail_days_at_date = db_services.AvailDay.get_all_from__plan_period_date(plan_period_id, e.date)
            date_casts[e.date] = DateCast(e.date, avail_days_at_date)
        date_casts[e.date].add_appointment(e)

    for date_cast in date_casts.values():
        date_cast.initialize_cast()

    for date_cast in date_casts.values():
        for appointment in date_cast.appointments:
            print(appointment)
        print('--------------------------------------------------------------------')
