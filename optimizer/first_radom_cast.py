import dataclasses
import datetime
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


if __name__ == '__main__':
    plan_period_id = UUID('0923404BCA2A47579ADE85188CF4EA7F')

    plan_period = db_services.PlanPeriod.get(plan_period_id)
    events = get_all_events_from__plan_period(plan_period_id)

    for e in events:
        persons_at_date = get_persons_of_team_at_date(plan_period.team.id, e.date)
        avail_days_at_date = db_services.AvailDay.get_all_from__plan_period_date(plan_period_id, e.date)
        print(e.date, e.time_of_day.name, e.location_plan_period.location_of_work.name,
              f'{[(avd.actor_plan_period.person.f_name, str(AvailDayParts(avd))) for avd in avail_days_at_date]}')
