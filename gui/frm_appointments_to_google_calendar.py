from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QDialogButtonBox

from database import schemas


class DlgSendAppointmentsToGoogleCal(QDialog):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent)
        self.setWindowTitle('Termine zu Google-Kalendern übertragen')
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

        self.lb_description = QLabel(f'<h4>Team: {self.plan.plan_period.team.name}<br>'
                                     f'Zeitraum: {self.text_time_span}</h4>'
                                     f'<p>Möchten Sie die Termine dieses Zeitraums<br>'
                                     'in die entsprechenden Google-Kalender der Mitarbeiter eintragen?<br>'
                                     'Bei diesem Vorgang werden vorhandene Termine dieses Zeitraums '
                                     'aus den Kalendern entfernt.</p>')
        self.layout_head.addWidget(self.lb_description)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _setup_data(self):
        self.text_time_span = f'{self.plan.plan_period.start:%d.%m.%y} - {self.plan.plan_period.end:%d.%m.%y}'
