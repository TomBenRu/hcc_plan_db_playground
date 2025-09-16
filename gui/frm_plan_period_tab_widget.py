import datetime
from uuid import UUID

from PySide6.QtWidgets import QWidget


class PlanPeriodTabWidget(QWidget):
    def __init__(self, parent: QWidget | None, plan_period_id: UUID, period_start: datetime.date = None,
                 period_end: datetime.date = None):
        """
        Widget für einen Planungszeitraum mit Sub-Tabs für Locations und Employees
        Args:
            parent: Übergeordnetes Widget
            plan_period_id: ID des Planungszeitraums
            period_start: Startdatum des Planungszeitraums (zur Anzeige in der StatusBar des Hauptfensters)
            period_end: Enddatum des Planungszeitraums (zur Anzeige in der StatusBar des Hauptfensters)
        """
        super().__init__(parent=parent)

        self.plan_period_id = plan_period_id
        self.period_start = period_start
        self.period_end = period_end
