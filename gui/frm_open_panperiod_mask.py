from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QComboBox, QDialogButtonBox

from database import db_services, schemas
from gui.custom_widgets.tabbars import TabBar


class DlgOpenPlanPeriodMask(QDialog):
    def __init__(self, parent: QWidget | None, team_id: UUID, tabs_planungsmasken: TabBar):
        super().__init__(parent=parent)

        self.team_id = team_id
        self.tabs_planungsmasken = tabs_planungsmasken
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.plan_periods: list[schemas.PlanPeriodShow] = []
        self.curr_plan_period_id: UUID | None = None
        self.combo_plan_periods = QComboBox()
        self.layout.addWidget(self.combo_plan_periods)
        self.fill_combo_plan_periods()

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def fill_combo_plan_periods(self):
        self.plan_periods = sorted((pp for pp in db_services.PlanPeriod.get_all_from__team(self.team_id)
                                    if pp.id not in {self.tabs_planungsmasken.widget(i).plan_period_id
                                                     for i in range(self.tabs_planungsmasken.count())}
                                    and not pp.prep_delete),
                                   key=lambda x: x.start, reverse=True)
        for pp in self.plan_periods:
            self.combo_plan_periods.addItem(f'{pp.start:%d.%m.%y} - {pp.end:%d.%m.%y}', pp.id)

    def accept(self):
        self.curr_plan_period_id = self.combo_plan_periods.currentData()
        super().accept()
