import dataclasses
import datetime
import random
import time
from typing import Literal, Self, Optional
from uuid import UUID
from database import db_services, schemas
from optimizer.signal_handling import handler_event_for_plan_period_cast, EventSignalData


class EventGroupCast:
    def __init__(self, event_group: schemas.EventGroupShow, parent_group: Optional['EventGroupCast'], level: int,
                 active: bool = False):
        self.active = active
        self.level = level
        self.event_group = event_group
        self.parent_group: 'EventGroupCast' = parent_group
        self.child_groups: list['EventGroupCast'] = []
        self.active_groups: list['EventGroupCast'] = []

        self.fill_child_groups()

    def fill_child_groups(self):
        for event_group in self.event_group.event_groups:
            event_group = db_services.EventGroup.get(event_group.id)
            new_event_group_cast = EventGroupCast(event_group, self, self.level + 1)
            self.child_groups.append(new_event_group_cast)
            if event_group.event:
                event = db_services.Event.get(event_group.event.id)
                handler_event_for_plan_period_cast.send_new_event(EventSignalData(event, False))

    def initialize_first_cast(self):
        if self.event_group.event:
            return
        for _ in range(self.event_group.nr_event_groups or len(self.event_group.event_groups)):
            child: 'EventGroupCast' = random.choice(self.child_groups)
            self.child_groups.remove(child)
            self.active_groups.append(child)
            child.active = True
            child.initialize_first_cast()
            if child.event_group.event:
                event = db_services.Event.get(child.event_group.event.id)
                handler_event_for_plan_period_cast.send_new_event(EventSignalData(event, True))


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
        # fixme: zu umständlich
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


class TimeOfDayCast:
    def __init__(self, date: datetime.date, time_of_day_enum: schemas.TimeOfDayEnum,
                 avail_days: list[schemas.AvailDayShow | None]):
        self.date = date
        self.time_of_day_enum = time_of_day_enum
        self.appointments_active: list[AppointmentCast] = []
        self.appointments_pool: list[AppointmentCast] = []
        self.avail_days = avail_days

    def add_appointment_to_pool(self, appointment: AppointmentCast):
        self.appointments_pool.append(appointment)

    def add_appointment_to_activ(self, appointment: AppointmentCast):
        self.appointments_active.append(appointment)

    def add_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.append(avail_day)

    def remove_avail_day(self, avail_day: schemas.AvailDayShow | None):
        self.avail_days.remove(avail_day)

    def pick_random_appointments(self, nr_appointments: int) -> list[AppointmentCast]:
        if not self.appointments_active:
            return []
        return [random.choice(self.appointments_active) for _ in range(nr_appointments)]

    def pick_random_avail_day(self) -> schemas.AvailDayShow | None:
        return random.choice(self.avail_days)

    def initialize_first_cast(self):  # fixme: zu umständlich
        appointments_indexes = list(range(len(self.appointments_active)))
        avail_days_indexes = list(range(len(self.avail_days)))
        random.shuffle(avail_days_indexes)

        avd_to_remove_indexes = []
        while appointments_indexes and avail_days_indexes:
            avd_idx = avail_days_indexes.pop()
            appointment_idx = random.choice(appointments_indexes)
            result = self.appointments_active[appointment_idx].add_avail_day_first_cast(self.avail_days[avd_idx])
            if result == 'full':
                avail_days_indexes.append(avd_idx)
                appointments_indexes.remove(appointment_idx)
            elif result == 'same person':
                avail_days_indexes.append(avd_idx)
            else:
                avd_to_remove_indexes.append(avd_idx)
        self.avail_days = [avd for idx, avd in enumerate(self.avail_days) if idx not in avd_to_remove_indexes]

    def __str__(self):
        return '\n'.join([str(appointment) for appointment in self.appointments_active])


class PlanPeriodCast:
    def __init__(self, plan_period_id: UUID, ):

        self.plan_period_id = plan_period_id
        self.time_of_day_casts: dict[(datetime.date, int), TimeOfDayCast] = {}
        handler_event_for_plan_period_cast.signal_new_event.connect(lambda e: self.generate_time_of_day_casts(e))

    def generate_time_of_day_casts(self, event_signal_data: EventSignalData):
        key = (event_signal_data.event.date, event_signal_data.event.time_of_day.time_of_day_enum.time_index)
        if not event_signal_data.move_to_active:
            if not self.time_of_day_casts.get(key):
                events_at_time_of_day = db_services.Event.get_all_from__plan_period_date_time_of_day(
                    self.plan_period_id, event_signal_data.event.date,
                    event_signal_data.event.time_of_day.time_of_day_enum.time_index
                )
                location_of_work_ids = {e.location_plan_period.location_of_work.id for e in events_at_time_of_day}
                avail_days_fits__date_time_of_day = (
                    db_services.AvailDay.get_all_from__plan_period__date__time_of_day__location_prefs(
                        self.plan_period_id, event_signal_data.event.date,
                        event_signal_data.event.time_of_day.time_of_day_enum.time_index,
                        location_of_work_ids)
                )
                self.time_of_day_casts[key] = TimeOfDayCast(
                    event_signal_data.event.date, event_signal_data.event.time_of_day.time_of_day_enum,
                    avail_days_fits__date_time_of_day
                )
            appointment = AppointmentCast(event_signal_data.event)
            self.time_of_day_casts[key].add_appointment_to_pool(appointment)
        if event_signal_data.move_to_active:
            appointment_to_move = next(
                (a for a in self.time_of_day_casts[key].appointments_pool
                 if a.event == event_signal_data.event))
            self.time_of_day_casts[key].appointments_pool.remove(appointment_to_move)
            self.time_of_day_casts[key].add_appointment_to_activ(appointment_to_move)
            self.time_of_day_casts[key].avail_days += [None] * appointment_to_move.event.cast_group.nr_actors

    def pick_random_time_of_day_cast(self) -> TimeOfDayCast:
        return random.choice(list(self.time_of_day_casts.values()))
    
    def calculate_initial_casts(self):
        for time_of_day_cast in self.time_of_day_casts.values():
            time_of_day_cast.initialize_first_cast()

    def __str__(self):
        return '\n----------------\n'.join(sorted(str(tod_cast) for tod_cast in self.time_of_day_casts.values()))
