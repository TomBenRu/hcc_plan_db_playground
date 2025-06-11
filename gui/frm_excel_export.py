from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QDialogButtonBox, QCheckBox

from database import schemas
from tools.helper_functions import date_to_string


class DlgPlanToXLSX(QDialog):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Export Plan to Excel'))
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

        self.lb_description = QLabel(
            self.tr('<h4>Team: {team_name}<br>'
                   'Period: {time_span}</h4>'
                   '<p>Do you want to export the plan for this period<br>'
                   'as an Excel file?<br>'
                   'You can choose whether appointment notes should be entered directly<br>'
                   'into the fields of the respective appointments.</p>').format(
                       team_name=self.plan.plan_period.team.name,
                       time_span=self.text_time_span))

        self.layout_head.addWidget(self.lb_description)

        self.check_notes_in_empty_fields = QCheckBox(
            self.tr('Enter notes in fields without assignments'))
        self.check_notes_in_empty_fields.setChecked(True)

        self.check_notes_in_employee_fields = QCheckBox(
            self.tr('Enter notes in fields with assignments'))
        self.check_notes_in_employee_fields.setChecked(False)

        self.layout_body.addWidget(self.check_notes_in_empty_fields)
        self.layout_body.addWidget(self.check_notes_in_employee_fields)

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _setup_data(self):
        self.text_time_span = f'{date_to_string(self.plan.plan_period.start)} - {date_to_string(self.plan.plan_period.end)}'

    @property
    def note_in_empty_fields(self):
        return self.check_notes_in_empty_fields.isChecked()

    @property
    def note_in_employee_fields(self):
        return self.check_notes_in_employee_fields.isChecked()
