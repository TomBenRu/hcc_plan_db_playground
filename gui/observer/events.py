import datetime

from py_events import Event

from database import schemas


class CustomEvent(Event):
    def __init__(self, data: object | None = None):
        super().__init__()

        self.data = data


class ReloadActorPlanPeriod(Event):
    def __init__(self, actor_plan_period: schemas.ActorPlanPeriodShow = None, date: datetime.date = None):
        self.actor_plan_period = actor_plan_period
        self.date = date
        super().__init__()


class ReloadActorPlanPeriodInActorFrmPlanPeriod(Event):
    def __init__(self):
        super().__init__()
        ...
