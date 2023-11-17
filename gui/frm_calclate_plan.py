from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QComboBox, QDialogButtonBox, QMessageBox

import sat_solver.solver_main
from database import db_services


class Calculate(QDialog):
    def __init__(self, parent: QWidget, team_id: UUID):
        super().__init__(parent)

        self.team_id = team_id
        self.team = db_services.Team.get(team_id)
        self.curr_plan_period_id: UUID | None = None
        self.setWindowTitle(f'Einsatzplan-Erstellung {self.team.name}')

        self.layout = QVBoxLayout(self)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel()
        self.layout_head.addWidget(self.lb_explanation)
        self.lb_combo_plan_periods = QLabel('Wählen Sie den entsprechenden Zeitraum für die Planung:')
        self.layout_body.addWidget(self.lb_combo_plan_periods)
        self.combo_plan_periods = QComboBox()
        self.layout_body.addWidget(self.combo_plan_periods)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                                           | QDialogButtonBox.StandardButton.Cancel)
        self.layout_foot.addWidget(self.button_box)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.fill_out_widgets()

    def accept(self):
        if not self.curr_plan_period_id:
            QMessageBox.critical(self, 'Zeitraum', 'Bitte wählen Sie zuerst einen Zeitraum.')
            return
        sat_solver.solver_main.solve(self.curr_plan_period_id)
        super().accept()

    def fill_out_widgets(self):
        self.lb_explanation.setText('Sie können automatisch Spielpläne für einen gewählten Planungszeitraum erstellen.')

        plan_periods = sorted([pp for pp in self.team.plan_periods if not pp.prep_delete],
                              key=lambda x: x.start, reverse=True)
        for plan_period in plan_periods:
            self.combo_plan_periods.addItem(f'{plan_period.start:%d.%m.%y} - {plan_period.end:%d.%m.%y}',
                                            plan_period.id)
        self.combo_plan_periods.currentIndexChanged.connect(self.combo_index_changed)
        self.combo_index_changed()

    def combo_index_changed(self):
        self.curr_plan_period_id = self.combo_plan_periods.currentData()
