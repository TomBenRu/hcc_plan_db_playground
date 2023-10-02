import dataclasses

from PySide6.QtCore import QObject, Signal

from database import schemas


@dataclasses.dataclass
class EventSignalData:
    event: schemas.EventShow
    move_to_active: bool


class HandlerEventForPlanPeriodCast(QObject):
    signal_new_event = Signal(object)

    def send_new_event(self, event_signal_data: EventSignalData):
        self.signal_new_event.emit(event_signal_data)


class HandlerSwitchAppointmentForTimeOfDayCast(QObject):
    signal_switch_appointment = Signal(object)

    def switch_appointment(self, event_signal_data: EventSignalData):
        self.signal_switch_appointment.emit(event_signal_data)


handler_event_for_plan_period_cast = HandlerEventForPlanPeriodCast()
