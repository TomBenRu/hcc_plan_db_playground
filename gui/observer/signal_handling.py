import datetime
from dataclasses import dataclass

from PySide6.QtCore import Signal, QObject

from database import schemas


@dataclass
class DataActorPPWithDate:
    actor_plan_period: schemas.ActorPlanPeriodShow
    date: datetime.date | None = None


class Handler(QObject):

    signal_reload_actor_pp__avail_configs = Signal(object)
    signal_reload_actor_pp__frm_actor_plan_period = Signal(object)

    def reload_actor_pp__avail_configs(self, data: DataActorPPWithDate):
        self.signal_reload_actor_pp__avail_configs.emit(data)

    def reload_actor_pp__frm_actor_plan_period(self, data: schemas.ActorPlanPeriodShow = None):
        self.signal_reload_actor_pp__frm_actor_plan_period.emit(data)


handler = Handler()
