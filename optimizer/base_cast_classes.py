import datetime
from abc import ABC, abstractmethod
from typing import Optional, Literal
from uuid import UUID

from commands import command_base_classes
from database import schemas, db_services
from optimizer.signal_handling import handler_event_for_plan_period_cast, EventSignalData


class BaseEventGroupCast(ABC):
    def __init__(self, event_group: schemas.EventGroupShow, parent_group: Optional['BaseEventGroupCast'], level: int,
                 active: bool = False):
        self.active = active
        self.level = level
        self.event_group: schemas.EventGroupShow = event_group
        self.event_of_event_group = db_services.Event.get(event_group.event.id) if event_group.event else None
        self.parent_group: 'BaseEventGroupCast' = parent_group
        self.child_groups: set['BaseEventGroupCast'] = set()
        self.active_groups: set['BaseEventGroupCast'] = set()

        self.group_cast_level_done = False

        self.controller = command_base_classes.ContrExecUndoRedo()

    @abstractmethod
    def fill_child_groups(self):
        ...

    @abstractmethod
    def initialize_first_cast(self):
        ...

    @abstractmethod
    def switch_event_group_casts(self, nr_to_switch: int):
        ...

    @abstractmethod
    def undo_switch_event_group_casts(self):
        ...

    @abstractmethod
    def set_inaktive(self):
        ...

    @abstractmethod
    def set_active(self):
        ...

    @abstractmethod
    def put_to_group_levels(self, level: int | None):
        ...


class BaseAppointmentCast(ABC):
    def __init__(self, event: schemas.EventShow):

        self.event = event
        self.avail_days: list[schemas.AvailDayShow] = []

    @abstractmethod
    def add_avail_day(self, avail_day: schemas.AvailDayShow | None) -> None:
        ...

    @abstractmethod
    def remove_avail_day(self, avail_day: schemas.AvailDayShow | None) -> None:
        ...

    @abstractmethod
    def pick_random_avail_day(self) -> schemas.AvailDayShow | None:
        ...

    @abstractmethod
    def add_avail_day_first_cast(self, avail_day: schemas.AvailDayShow) -> Literal['filled', 'same person', 'full']:
        ...


class BaseTimeOfDayCast:
    def __init__(self, date: datetime.date, time_of_day_enum: schemas.TimeOfDayEnum,
                 avail_days: list[schemas.AvailDayShow | None]):
        self.date = date
        self.time_of_day_enum = time_of_day_enum
        self.appointments_active: list[BaseAppointmentCast] = []
        self.appointments_pool: list[BaseAppointmentCast] = []
        self.avail_days = avail_days

    @abstractmethod
    def add_appointment_to_pool(self, appointment: BaseAppointmentCast):
        ...

    @abstractmethod
    def add_appointment_to_activ(self, appointment: BaseAppointmentCast):
        ...

    @abstractmethod
    def add_avail_day(self, avail_day: schemas.AvailDayShow | None):
        ...

    @abstractmethod
    def remove_avail_day(self, avail_day: schemas.AvailDayShow | None):
        ...

    @abstractmethod
    def pick_random_appointments(self, nr_appointments: int) -> list[BaseAppointmentCast]:
        ...

    @abstractmethod
    def pick_random_avail_day(self) -> schemas.AvailDayShow | None:
        ...

    @abstractmethod
    def initialize_first_cast(self):
        ...


class BasePlanPeriodCast(ABC):
    def __init__(self, plan_period_id: UUID):

        self.plan_period_id = plan_period_id
        self.time_of_day_casts: dict[(datetime.date, int), BaseTimeOfDayCast] = {}
        handler_event_for_plan_period_cast.signal_new_event.connect(lambda e: self.generate_time_of_day_casts(e))

    @abstractmethod
    def generate_time_of_day_casts(self, event_signal_data: EventSignalData):
        ...

    @abstractmethod
    def pick_random_time_of_day_cast(self) -> BaseTimeOfDayCast:
        ...

    @abstractmethod
    def calculate_initial_casts(self):
        ...
