from PySide6.QtCore import Signal, QObject

from database import schemas


class Handler(QObject):

    reload_actor_plan_period__avail_configs = Signal(object)
    reload_actor_plan_period__frm_actor_plan_period = Signal(object)

    def reload_actor_pp__avail_configs(self, data: schemas.ActorPlanPeriodShow):
        self.reload_actor_plan_period__avail_configs.emit(data)

    def reload_actor_pp__frm_actor_plan_period(self, data: schemas.ActorPlanPeriodShow):
        self.reload_actor_plan_period__avail_configs.emit(data)


handler = Handler()
