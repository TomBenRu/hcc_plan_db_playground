import dataclasses
import datetime
import random
import time
from typing import Literal, Self, Optional
from uuid import UUID

from commands.optimizer_commands import pop_out_pop_in_commands
from database import db_services, schemas
from optimizer.base_cast_classes import BaseEventGroupCast, BaseAppointmentCast, BasePlanPeriodCast, BaseTimeOfDayCast
from optimizer.signal_handling import handler_event_for_plan_period_cast, EventSignalData, \
    handler_switch_appointment_for_time_of_day_cast


class EventGroupCast(BaseEventGroupCast):
    def __init__(self, event_group: schemas.EventGroupShow, parent_group: Optional['EventGroupCast'], level: int,
                 active: bool = False):
        super().__init__(event_group, parent_group, level, active)

        self.fill_child_groups()

    def fill_child_groups(self):
        for event_group in self.event_group.event_groups:
            event_group = db_services.EventGroup.get(event_group.id)
            new_event_group_cast = EventGroupCast(event_group, self, self.level + 1)
            # input(f'{new_event_group_cast.event_of_event_group=}')
            self.child_groups.add(new_event_group_cast)
            if event := new_event_group_cast.event_of_event_group:
                handler_event_for_plan_period_cast.send_new_event(EventSignalData(event, False))

    def initialize_first_cast(self):
        if self.event_group.event:
            return
        for _ in range(self.event_group.nr_event_groups or len(self.event_group.event_groups)):
            child: 'EventGroupCast' = random.choice(list(self.child_groups))
            self.child_groups.remove(child)
            self.active_groups.add(child)
            child.active = True
            child.initialize_first_cast()
            if event := child.event_of_event_group:
                handler_event_for_plan_period_cast.send_new_event(EventSignalData(event, True))

    def switch_event_group_casts(self, nr_to_switch: int):
        self.controller.undo_stack.clear()
        if ((not self.event_group.event)
                and self.event_group.nr_event_groups
                and self.event_group.nr_event_groups < len(self.event_group.event_groups)):
            for _ in range(min(nr_to_switch, self.event_group.nr_event_groups)):
                child_group_to_pop: 'EventGroupCast' = random.choice(list(self.child_groups))
                active_group_to_pop: 'EventGroupCast' = random.choice(list(self.active_groups))
                self.controller.execute(pop_out_pop_in_commands.SwitchEventGroupCast(
                    self, child_group_to_pop, active_group_to_pop))

    def set_inaktive(self):
        self.active = False
        if self.event_group.event:
            event = db_services.Event.get(self.event_group.event.id)
            handler_switch_appointment_for_time_of_day_cast.switch_appointment(EventSignalData(event, False))
        else:
            for evg in self.active_groups:
                self.active_groups.remove(evg)
                self.child_groups.add(evg)
                evg.set_inaktive()

    def set_active(self):
        self.active = True
        if self.event_group.event:
            event = db_services.Event.get(self.event_group.event.id)
            handler_switch_appointment_for_time_of_day_cast.switch_appointment(EventSignalData(event, True))
        else:
            for evg in self.child_groups:
                self.child_groups.remove(evg)
                self.active_groups.add(evg)
                evg.set_active()


class AppointmentCast(BaseAppointmentCast):
    def __init__(self, event: schemas.EventShow):
        super().__init__(event)

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


class TimeOfDayCast(BaseTimeOfDayCast):
    def __init__(self, date: datetime.date, time_of_day_enum: schemas.TimeOfDayEnum,
                 avail_days: list[schemas.AvailDayShow | None]):
        super().__init__(date, time_of_day_enum, avail_days)

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


class PlanPeriodCast(BasePlanPeriodCast):
    def __init__(self, plan_period_id: UUID):
        super().__init__(plan_period_id)



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
