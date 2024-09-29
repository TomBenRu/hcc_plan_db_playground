from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QDialogButtonBox

from database import schemas


class DlgSendAppointmentsToGoogleCal(QDialog):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent)
        self.plan = plan

        self._setup_data()
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(30)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(f'Möchten Sie die Termine des Zeitraums {self.text_time_span}\n'
                                     'in die entsprechenden Google-Kalender der Mitarbeiter eintragen?\n'
                                     'Bei diesem Vorgang werden vorhandene Termine dieses Zeitraums\n'
                                     'aus den Kalendern entfernt.')
        self.layout_head.addWidget(self.lb_description)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _setup_data(self):
        self.text_time_span = f'{self.plan.plan_period.start:%d.%m.%y} - {self.plan.plan_period.end:%d.%m.%y}'
