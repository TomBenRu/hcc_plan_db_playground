from database import schemas
from gui.commands.command_base_classes import Command
from optimizer.first_radom_cast import AppointmentCast, PlanPeriodCast


class PopOutAvailDay(Command):
    def __init__(self, plan_period_cast: PlanPeriodCast, appointment_cast: AppointmentCast,
                 avail_day_to_pop: schemas.AvailDayShow | None):
        self.plan_period_cast = plan_period_cast
        self.appointment_cast = appointment_cast
        self.avail_day_to_pop = avail_day_to_pop

    def execute(self):
        self.appointment_cast.remove_avail_day(self.avail_day_to_pop)
        self.plan_period_cast.date_casts[self.avail_day_to_pop.date].add_avail_day(self.avail_day_to_pop)

    def undo(self):
        self.appointment_cast.add_avail_day(self.avail_day_to_pop)
        self.plan_period_cast.date_casts[self.avail_day_to_pop.date].remove_avail_day(self.avail_day_to_pop)

    def redo(self):
        self.appointment_cast.remove_avail_day(self.avail_day_to_pop)
        self.plan_period_cast.date_casts[self.avail_day_to_pop.date].add_avail_day(self.avail_day_to_pop)


class PutInAvailDay(Command):
    def __init__(self, plan_period_cast: PlanPeriodCast, appointment_cast: AppointmentCast,
                 avail_day_to_put_in: schemas.AvailDayShow | None):
        self.plan_period_cast = plan_period_cast
        self.appointment_cast = appointment_cast
        self.avail_day_to_put_in = avail_day_to_put_in

    def execute(self):
        self.appointment_cast.add_avail_day(self.avail_day_to_put_in)
        self.plan_period_cast.date_casts[self.avail_day_to_put_in.date].remove_avail_day(self.avail_day_to_put_in)

    def undo(self):
        self.appointment_cast.remove_avail_day(self.avail_day_to_put_in)
        self.plan_period_cast.date_casts[self.avail_day_to_put_in.date].add_avail_day(self.avail_day_to_put_in)

    def redo(self):
        self.appointment_cast.add_avail_day(self.avail_day_to_put_in)
        self.plan_period_cast.date_casts[self.avail_day_to_put_in.date].remove_avail_day(self.avail_day_to_put_in)



