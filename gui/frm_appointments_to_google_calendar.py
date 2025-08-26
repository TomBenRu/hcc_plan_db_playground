from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QDialogButtonBox

from database import schemas
from tools.helper_functions import date_to_string, setup_form_help


class DlgSendAppointmentsToGoogleCal(QDialog):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent)
        self.setWindowTitle(self.tr('Transfer Appointments to Google Calendar'))
        self.plan = plan

        self._setup_data()
        self._setup_ui()
        
        # F1 Help Integration
        setup_form_help(self, "google_calendar", add_help_button=True)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(30)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(
            self.tr('<h4>Team: {team_name}<br>'
                   'Period: {time_span}</h4>'
                   '<p>Do you want to add the appointments of this period<br>'
                   'to the corresponding Google Calendars of the employees?<br>'
                   'During this process, existing appointments of this period '
                   'will be removed from the calendars.</p>').format(
                team_name=self.plan.plan_period.team.name,
                time_span=self.text_time_span
            ))
        self.layout_head.addWidget(self.lb_description)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Yes | QDialogButtonBox.StandardButton.No)
        self.layout_foot.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _setup_data(self):
        self.text_time_span = (f'{date_to_string(self.plan.plan_period.start)} '
                               f'- {date_to_string(self.plan.plan_period.end)}')
