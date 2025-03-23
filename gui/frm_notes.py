from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QTextEdit, QDialogButtonBox, \
    QPushButton, QCheckBox

from database import db_services, schemas


class DlgPlanPeriodNotes(QDialog):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr('Plan Information'))
        self.plan = plan

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
            self.tr('Enter the information that should appear\nin the generated schedules\n'
                   'Plan: {plan}\n'
                   'Team: {team}\n'
                   'Planning period: {start} - {end}').format(
                plan=self.plan.name,
                team=self.plan.plan_period.team.name,
                start=self.plan.plan_period.start.strftime("%d.%m.%y"),
                end=self.plan.plan_period.end.strftime("%d.%m.%y")))
        self.layout_head.addWidget(self.lb_explanation)
        self.text_info = QTextEdit()
        self.text_info.setText(self.plan.notes)
        self.bt_reset_from_plan_period = QPushButton(self.tr('Reset from Planning Period'))
        self.bt_reset_from_plan_period.clicked.connect(self.reset_from_plan_period)
        self.chk_sav_to_plan_period = QCheckBox(self.tr('Also save as Planning Period information'))
        self.layout_body.addWidget(self.text_info)
        self.layout_body.addWidget(self.bt_reset_from_plan_period)
        self.layout_body.addWidget(self.chk_sav_to_plan_period)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def reset_from_plan_period(self):
        self.text_info.setText(self.plan.plan_period.notes)

    @property
    def notes(self):
        return self.text_info.toPlainText()


class DlgTeamNotes(QDialog):
    def __init__(self, parent: QWidget, team: schemas.TeamShow):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr('Team Information'))
        self.team = team

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
            self.tr('Enter information relevant for the team.\n'
                   'This will be copied to newly created planning periods.\n'
                   'Team: {team}').format(team=self.team.name))
        self.layout_head.addWidget(self.lb_explanation)
        self.text_info = QTextEdit()
        self.text_info.setText(self.team.notes or '')
        self.layout_body.addWidget(self.text_info)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    @property
    def notes(self):
        return self.text_info.toPlainText()


class DlgEventNotes(QDialog):
    def __init__(self, parent: QWidget, event: schemas.EventShow, multiple_events: bool = False):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr('Event Notes'))
        self.event = event
        self.multiple_events = multiple_events

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        events_text = self.tr('events') if self.multiple_events else self.tr('event')
        time_text = self.tr('all times of day') if self.multiple_events else self.event.time_of_day.name

        self.lb_explanation = QLabel(
            self.tr('Enter information relevant for the {events_type}.\n'
                   'This will be copied to linked appointments in the schedules.\n'
                   '{events_type}: {date} ({time}) - {location}').format(
                events_type=events_text.capitalize(),
                date=self.event.date.strftime("%d.%m.%y"),
                time=time_text,
                location=self.event.location_plan_period.location_of_work.name_an_city))
        self.layout_head.addWidget(self.lb_explanation)
        self.text_info = QTextEdit()
        self.text_info.setText(self.event.notes or '')
        self.layout_body.addWidget(self.text_info)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    @property
    def notes(self):
        return self.text_info.toPlainText()


class DlgAppointmentNotes(QDialog):
    def __init__(self, parent: QWidget, appointment: schemas.Appointment):
        super().__init__(parent=parent)
        self.setWindowTitle(self.tr('Appointment Information'))
        self.appointment = appointment

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("background-color: none")
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel(
            self.tr('Enter information relevant for the appointment.\n'
                   'This will be included in the generated Excel file of the schedule.\n'
                   'Appointment: {date} ({time}) - {location}').format(
                date=self.appointment.event.date.strftime("%d.%m.%y"),
                time=self.appointment.event.time_of_day.name,
                location=self.appointment.event.location_plan_period.location_of_work.name_an_city))
        self.layout_head.addWidget(self.lb_explanation)
        self.text_info = QTextEdit()
        self.text_info.setText(self.appointment.notes)
        self.bt_reset_from_event = QPushButton(self.tr('Reset from Planning Event'))
        self.bt_reset_from_event.clicked.connect(self.reset_from_event)
        self.layout_body.addWidget(self.text_info)
        self.layout_body.addWidget(self.bt_reset_from_event)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def reset_from_event(self):
        self.text_info.setText(self.appointment.event.notes)

    @property
    def notes(self):
        return self.text_info.toPlainText()
