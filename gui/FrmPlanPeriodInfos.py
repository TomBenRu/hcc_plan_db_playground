from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QTextEdit, QDialogButtonBox, \
    QPushButton, QCheckBox

from database import db_services, schemas


class DlgPlanPeriodInfos(QDialog):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent=parent)
        self.setWindowTitle('Plan-Infos')
        self.plan = plan

        self._prepare_data()
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel(
            f'Geben Sie hier die Informationen ein,\ndie später in den erstellten Plänen\n'
            f'des Plans: {self.plan.name}\n'
            f'des Teams: {self.plan.plan_period.team.name}\nerscheinen sollen.\n'
            f'Planungszeitraum: {self.plan.plan_period.start:%d.%m.%y} - {self.plan.plan_period.end:%d.%m.%y}')
        self.layout_head.addWidget(self.lb_explanation)
        self.text_info = QTextEdit()
        self.text_info.setText(self.plan.notes)
        self.bt_reset_from_plan_period = QPushButton('Reset vom Planungszeitraum')
        self.bt_reset_from_plan_period.clicked.connect(self.reset_from_plan_period)
        self.chk_sav_to_plan_period = QCheckBox('Auch als Info des Planungszeitraums speichern')
        self.layout_body.addWidget(self.text_info)
        self.layout_body.addWidget(self.bt_reset_from_plan_period)
        self.layout_body.addWidget(self.chk_sav_to_plan_period)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _prepare_data(self):
        self.notes: str = ''

    def reset_from_plan_period(self):
        self.text_info.setText(self.plan.plan_period.notes)

    def accept(self):
        self.notes = self.text_info.toPlainText()
        super().accept()
