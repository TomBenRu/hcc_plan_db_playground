from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QComboBox, QDialogButtonBox, QLabel, QGroupBox, QFormLayout

from database import db_services, schemas
from gui.custom_widgets.tabbars import TabBar


class DlgOpenPlanPeriodMask(QDialog):
    def __init__(self, parent: QWidget | None, team_id: UUID, tabs_planning_masks: TabBar):
        super().__init__(parent=parent)

        self.setWindowTitle(self.tr('Planning Masks'))

        self.team_id = team_id
        self.tabs_planning_masks = tabs_planning_masks
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.plan_periods: list[schemas.PlanPeriodShow] = []
        self.curr_plan_period_id: UUID | None = None

        self._set_layout()
        self.fill_combo_plan_periods()

    def _set_layout(self):
        self.lb_description = QLabel()
        self.lb_description.setText(self.tr('Please select the planning period\n'
                                          'for which the planning masks should be opened.'))
        self.layout.addWidget(self.lb_description)
        self.group_plan_periods = QGroupBox(self.tr('Planning Periods'))
        self.layout.addWidget(self.group_plan_periods)
        self.layout_plan_periods = QFormLayout()
        self.group_plan_periods.setLayout(self.layout_plan_periods)
        self.combo_plan_periods = QComboBox()
        self.layout_plan_periods.addRow(self.tr('select:'), self.combo_plan_periods)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.layout.addWidget(self.button_box)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def fill_combo_plan_periods(self):
        self.plan_periods = sorted((pp for pp in db_services.PlanPeriod.get_all_from__team_minimal(self.team_id)
                                    if pp.id not in {self.tabs_planning_masks.widget(i).plan_period_id
                                                     for i in range(self.tabs_planning_masks.count())}
                                    and not pp.prep_delete),
                                   key=lambda x: x.start, reverse=True)
        for pp in self.plan_periods:
            self.combo_plan_periods.addItem(f'{pp.start:%d.%m.%y} - {pp.end:%d.%m.%y}', pp.id)

    def accept(self):
        self.curr_plan_period_id = self.combo_plan_periods.currentData()
        super().accept()
