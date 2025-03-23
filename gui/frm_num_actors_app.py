from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QSpinBox, QDialogButtonBox, \
    QPushButton

from database import db_services


class DlgNumActorsApp(QDialog):
    def __init__(self, parent: QWidget, location_plan_period_id: UUID):
        super().__init__(parent)
        self.location_plan_period = db_services.LocationPlanPeriod.get(location_plan_period_id)
        self.parent = parent
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle(self.tr("Number of Employees per Event"))
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(20)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel(self.tr("Please enter the number of employees per event."))
        self.layout_head.addWidget(self.lb_explanation)
        self.spinbox_num_actors = QSpinBox()
        self.layout_body.addRow(self.tr("Number of employees:"), self.spinbox_num_actors)
        self.spinbox_num_actors.setMinimum(0)
        self.spinbox_num_actors.setValue(self.location_plan_period.nr_actors)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.bt_reset = QPushButton(self.tr("Reset"))
        self.bt_reset.setToolTip(self.tr('Resets the number of employees to the facility default value.'))
        self.bt_reset.clicked.connect(self.reset_num_actors)
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def reset_num_actors(self):
        self.spinbox_num_actors.setValue(self.location_plan_period.location_of_work.nr_actors)

    @property
    def num_actors(self) -> int:
        return self.spinbox_num_actors.value()
