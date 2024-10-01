from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QDialogButtonBox, QCheckBox

from database import schemas


class DlgPlanToXLSX(QDialog):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent)
        self.setWindowTitle('Export Plan zu Excel')
        self.plan = plan

        self._setup_data()
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(30)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_body.setSpacing(10)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(f'<h4>Team: {self.plan.plan_period.team.name}<br>'
                                     f'Zeitraum: {self.text_time_span}</h4>'
                                     f'<p>Möchten Sie den Plan dieses Zeitraums<br>'
                                     'als Excel-Datei exportieren?<br>'
                                     'Sie können auswählen, ob Terminanmerkungen direkt in die Felder<br>'
                                     'der betreffenden Termine eingetragen werden sollen.</p>')
        self.layout_head.addWidget(self.lb_description)
        self.check_notes_in_empty_fields = QCheckBox('Anmerkungen in Felder ohne Besetzung eintragen')
        self.check_notes_in_empty_fields.setChecked(False)
        self.check_notes_in_employee_fields = QCheckBox('Anmerkungen in Felder mit Besetzung eintragen')
        self.check_notes_in_empty_fields.setChecked(False)
        self.layout_body.addWidget(self.check_notes_in_empty_fields)
        self.layout_body.addWidget(self.check_notes_in_employee_fields)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _setup_data(self):
        self.text_time_span = f'{self.plan.plan_period.start:%d.%m.%y} - {self.plan.plan_period.end:%d.%m.%y}'

    @property
    def note_in_empty_fields(self):
        return self.check_notes_in_empty_fields.isChecked()

    @property
    def note_in_employee_fields(self):
        return self.check_notes_in_employee_fields.isChecked()
