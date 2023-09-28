from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QSpinBox, QDialogButtonBox, \
    QPushButton

from commands import command_base_classes
from commands.database_commands import actor_plan_period_commands
from database import db_services


class DlgRequestedAssignments(QDialog):
    def __init__(self, parent: QWidget, actor_plan_period_id: UUID):
        super().__init__(parent=parent)

        self.setWindowTitle('Anzahl gewünschter Termine')

        self.actor_plan_period_id = actor_plan_period_id
        self.actor_plan_period = db_services.ActorPlanPeriod.get(self.actor_plan_period_id)

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_info = QLabel()
        self.layout_head.addWidget(self.lb_info)

        self.spin_requested_assignments = QSpinBox()
        self.layout_body.addRow('Anzahl gewünschter Termine', self.spin_requested_assignments)

        self.bt_reset = QPushButton('Reset', clicked=self.reset)
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        self.setup_widgets()

    def reject(self) -> None:
        self.controller.undo_all()
        super().reject()

    def setup_widgets(self):
        self.lb_info.setText(f'Die Anzahl gewünschter Einsätze bezieht sich auf den gesamten Planungszeitraum\n'
                             f'von {self.actor_plan_period.plan_period.start: %d.%m.%Y} '
                             f'bis {self.actor_plan_period.plan_period.end:%d.%m.%Y}')
        self.spin_requested_assignments.setFixedWidth(40)
        self.spin_requested_assignments.setRange(0, 500)
        self.spin_requested_assignments.setValue(self.actor_plan_period.requested_assignments)
        self.spin_requested_assignments.valueChanged.connect(self.spin_requested_assignments_value_changed)

    def spin_requested_assignments_value_changed(self):
        self.controller.execute(actor_plan_period_commands.UpdateRequestedAssignments(
            self.actor_plan_period_id, self.spin_requested_assignments.value()))

    def reset(self):
        self.spin_requested_assignments.setValue(self.actor_plan_period.person.requested_assignments)
