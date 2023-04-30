import datetime

from py_events import Event


class CustomEvent(Event):
    def __init__(self, data: object | None = None):
        super().__init__()

        self.data = data


class ReloadActorPlanPeriod(Event):
    def __init__(self, date: datetime.date = None):
        self.date = date
        super().__init__()


class ReloadActorPlanPeriodInActorFrmPlanPeriod(Event):
    def __init__(self):
        super().__init__()
        ...
