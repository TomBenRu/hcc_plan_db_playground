import datetime

from PySide6.QtCore import QDate
from PySide6.QtWidgets import QDialog, QVBoxLayout, QCalendarWidget, QDialogButtonBox, QWidget

from gui.custom_widgets.custom_date_and_time_edit import CalendarLocale


class TeamAssignmentDateDialog(QDialog):
    def __init__(self, parent: QWidget, current_date: datetime.date | None = None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Team-Zuweisungsdatum")
        self.setMinimumWidth(300)
        self.current_date = current_date

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.calendar = CalendarLocale()
        layout.addWidget(self.calendar)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        if self.current_date:
            self.calendar.setSelectedDate(QDate(self.current_date.year, self.current_date.month, self.current_date.day))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
