from line_profiler_pycharm import profile

from database import schemas
from commands.command_base_classes import Command
from optimizer.first_radom_cast import AppointmentCast, PlanPeriodCast


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
