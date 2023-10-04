import random

from line_profiler_pycharm import profile

from database import schemas
from commands.command_base_classes import Command
from optimizer.base_cast_classes import BaseEventGroupCast, BaseAppointmentCast, BasePlanPeriodCast


class TimeOfDayCastPopOutAvailDay(Command):
    def __init__(self, plan_period_cast: BasePlanPeriodCast, appointment_cast: BaseAppointmentCast,
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
    def __init__(self, plan_period_cast: BasePlanPeriodCast, appointment_cast: BaseAppointmentCast,
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
    def __init__(self, event_group_cast: BaseEventGroupCast,
                 child_group_to_pop: BaseEventGroupCast, active_group_to_pop: BaseEventGroupCast):
        self.event_group_cast = event_group_cast
        self.child_group_to_pop = child_group_to_pop
        self.active_group_to_pop = active_group_to_pop

    def execute(self):
        self.event_group_cast.child_groups.remove(self.child_group_to_pop)
        self.event_group_cast.active_groups.remove(self.active_group_to_pop)
        self.event_group_cast.active_groups.add(self.child_group_to_pop)
        self.event_group_cast.child_groups.add(self.active_group_to_pop)
        self.active_group_to_pop.set_inaktive()
        self.child_group_to_pop.set_active()

    def undo(self):
        self.event_group_cast.active_groups.remove(self.child_group_to_pop)
        self.event_group_cast.child_groups.remove(self.active_group_to_pop)
        self.event_group_cast.active_groups.add(self.active_group_to_pop)
        self.event_group_cast.child_groups.add(self.child_group_to_pop)
        self.child_group_to_pop.set_inaktive()
        self.active_group_to_pop.set_active()

    def redo(self):
        self.event_group_cast.child_groups.remove(self.child_group_to_pop)
        self.event_group_cast.active_groups.remove(self.active_group_to_pop)
        self.event_group_cast.active_groups.add(self.child_group_to_pop)
        self.event_group_cast.child_groups.add(self.active_group_to_pop)
        self.active_group_to_pop.set_inaktive()
        self.child_group_to_pop.set_active()
