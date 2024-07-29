from uuid import UUID

from PySide6.QtWidgets import QWidget


class PlanPeriodTabWidget(QWidget):
    def __init__(self, parent: QWidget | None, plan_period_id: UUID):
        super().__init__(parent=parent)

        self.plan_period_id = plan_period_id
