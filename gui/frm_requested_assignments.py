from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QSpinBox, QDialogButtonBox, \
    QPushButton


class DlgRequestedAssignments(QDialog):
    def __init__(self, parent: QWidget, actor_plan_period_id: UUID):
        super().__init__(parent=parent)
        self.actor_plan_period_id = actor_plan_period_id

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

        self.bt_reset = QPushButton('Reset')
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.bt_reset, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.bt_reset.connect(self.reset)
