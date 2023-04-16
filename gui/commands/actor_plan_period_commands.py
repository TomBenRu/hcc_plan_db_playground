from uuid import UUID

from database import db_services, schemas
from gui.commands.command_base_classes import Command


class Update(Command):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow):
        self.new_data = actor_plan_period.copy()
        self.old_data = db_services.ActorPlanPeriod.get(actor_plan_period.id)

    def execute(self):
        db_services.ActorPlanPeriod.update(self.new_data)

    def undo(self):
        db_services.ActorPlanPeriod.update(self.old_data)

    def redo(self):
        db_services.ActorPlanPeriod.update(self.new_data)


class NewTimeOfDayStandard(Command):
    def __init__(self, actor_plan_period_id: UUID, time_of_day_id: UUID):
        self.actor_plan_period_id = actor_plan_period_id
        self.time_of_day_id = time_of_day_id
        self.old_t_o_d_standard_id = None

    def execute(self):
        _, self.old_t_o_d_standard_id = db_services.ActorPlanPeriod.new_time_of_day_standard(self.actor_plan_period_id,
                                                                                             self.time_of_day_id)

    def undo(self):
        db_services.ActorPlanPeriod.remove_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)
        if self.old_t_o_d_standard_id:
            db_services.ActorPlanPeriod.new_time_of_day_standard(self.actor_plan_period_id, self.old_t_o_d_standard_id)

    def redo(self):
        db_services.ActorPlanPeriod.new_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)


class RemoveTimeOfDayStandard(Command):
    def __init__(self, actor_plan_period_id: UUID, time_of_day_id: UUID):
        self.actor_plan_period_id = actor_plan_period_id
        self.time_of_day_id = time_of_day_id

    def execute(self):
        db_services.ActorPlanPeriod.remove_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)

    def undo(self):
        db_services.ActorPlanPeriod.new_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)

    def redo(self):
        db_services.ActorPlanPeriod.remove_time_of_day_standard(self.actor_plan_period_id, self.time_of_day_id)