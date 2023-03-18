from typing import Protocol, runtime_checkable
from uuid import UUID

from PySide6.QtWidgets import QComboBox, QWidget

from database import schemas


@runtime_checkable
class ManipulateTimeOfDays(Protocol):
    def __init__(self):
        self.project_id: UUID = UUID(None)
        self.cb_time_of_days: QComboBox = QComboBox
        self.time_of_days_to_delete: list[schemas.TimeOfDayShow] = []
        self.time_of_days_to_update: list[schemas.TimeOfDayShow] = []

    def fill_time_of_days(self):
        ...

