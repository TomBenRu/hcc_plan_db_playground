import random

from line_profiler_pycharm import profile

from database import schemas
from commands.command_base_classes import Command
from optimizer.first_radom_cast import AppointmentCast, PlanPeriodCast, EventGroupCast


class TimeOfDayCastPopOutAvailDay(Command):
    def __init__(self, plan_period_cast: PlanPeriodCast, appointment_cast: AppointmentCast,
                 avail_day_to_pop: schemas.AvailDayShow | None):
        self.plan_period_cast = plan_period_cast
        self.appointment_cast = appointment_cast
        self.avail_day_to_pop = avail_day_to_pop
        self.key_time_of_day_cast = (self.appointment_cast.event.date,
                                     self.appointment_cast.event.time_of_day.time_of_day_enum.time_index)

    def execute(self):
        self.appointment_cast.remove_avail_day(self.avail_day_to_pop)
        self.plan_period_cast.time_of_day_casts[self.key_time_of_day_cast].add_avail_day(self.avail_day_to_pop)

    def undo(self):
        self.appointment_cast.add_avail_day(self.avail_day_to_pop)
        self.plan_period_cast.time_of_day_casts[self.key_time_of_day_cast].remove_avail_day(self.avail_day_to_pop)

    def redo(self):
        self.appointment_cast.remove_avail_day(self.avail_day_to_pop)
        self.plan_period_cast.time_of_day_casts[self.key_time_of_day_cast].add_avail_day(self.avail_day_to_pop)


class TimeOfDayCastPutInAvailDay(Command):
    def __init__(self, plan_period_cast: PlanPeriodCast, appointment_cast: AppointmentCast,
                 avail_day_to_put_in: schemas.AvailDayShow | None):
        self.plan_period_cast = plan_period_cast
        self.appointment_cast = appointment_cast
        self.avail_day_to_put_in = avail_day_to_put_in
        self.key_time_of_day_cast = (self.appointment_cast.event.date,
                                     self.appointment_cast.event.time_of_day.time_of_day_enum.time_index)

    def execute(self):
        self.appointment_cast.add_avail_day(self.avail_day_to_put_in)
        self.plan_period_cast.time_of_day_casts[self.key_time_of_day_cast].remove_avail_day(self.avail_day_to_put_in)

    def undo(self):
        self.appointment_cast.remove_avail_day(self.avail_day_to_put_in)
        self.plan_period_cast.time_of_day_casts[self.key_time_of_day_cast].add_avail_day(self.avail_day_to_put_in)

    def redo(self):
        self.appointment_cast.add_avail_day(self.avail_day_to_put_in)
        self.plan_period_cast.time_of_day_casts[self.key_time_of_day_cast].remove_avail_day(self.avail_day_to_put_in)


class SwitchEventGroupCast(Command):
    def __init__(self, event_group_cast: EventGroupCast):
        self.event_group_cast = event_group_cast
        self.popped_child_group: EventGroupCast | None = None
        self.popped_active_group: EventGroupCast | None = None

    def execute(self):
        self.popped_child_group = self.event_group_cast.child_groups.pop(
            random.randrange(len(self.event_group_cast.child_groups)))
        self.popped_active_group = self.event_group_cast.active_groups.pop(
            random.randrange(len(self.event_group_cast.active_groups)))
        self.event_group_cast.active_groups.append(self.popped_child_group)
        self.event_group_cast.child_groups.append(self.popped_active_group)

    def undo(self):
        self.event_group_cast.active_groups.remove(self.popped_child_group)
        self.event_group_cast.child_groups.remove(self.popped_active_group)
        self.event_group_cast.active_groups.append(self.popped_active_group)
        self.event_group_cast.child_groups.append(self.popped_child_group)

    def redo(self):
        self.event_group_cast.active_groups.remove(self.popped_active_group)
        self.event_group_cast.child_groups.remove(self.popped_child_group)
        self.event_group_cast.active_groups.append(self.popped_child_group)
        self.event_group_cast.child_groups.append(self.popped_active_group)
