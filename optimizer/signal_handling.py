from PySide6.QtCore import QObject, Signal

from database import schemas


class HandlerEventForPlanPeriodCast(QObject):
    signal_new_event = Signal(object)

    def send_event_to_all_events(self, event: schemas.EventShow):
        self.signal_new_event.emit(event)


handler_event_for_plan_period_cast = HandlerEventForPlanPeriodCast()
