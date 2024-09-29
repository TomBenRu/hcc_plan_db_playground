from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QTextEdit, QDialogButtonBox, \
    QPushButton, QCheckBox

from database import db_services, schemas


class DlgPlanPeriodNotes(QDialog):
    def __init__(self, parent: QWidget, plan: schemas.PlanShow):
        super().__init__(parent=parent)
        self.setWindowTitle('Plan-Infos')
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

    def reset_from_plan_period(self):
        self.text_info.setText(self.plan.plan_period.notes)

    @property
    def notes(self):
        return self.text_info.toPlainText()


class DlgTeamNotes(QDialog):
    def __init__(self, parent: QWidget, team: schemas.TeamShow):
        super().__init__(parent=parent)
        self.setWindowTitle('Team-Infos')
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
            f'Geben Sie hier die Informationen ein, die für das Team relevant sind.\n'
            f'Diese werden in neu erstellten Planperioden übernommen.\n'
            f'Team: {self.team.name}')
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
    def __init__(self, parent: QWidget, event: schemas.EventShow):
        super().__init__(parent=parent)
        self.setWindowTitle('Team-Infos')
        self.event = event

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
            f'Geben Sie hier die Informationen ein, die für den Termin relevant sind.\n'
            f'Diese werden in die damit verknüpften erstellten Termine der Pläne übernommen.\n'
            f'Termin: {self.event.date:%d.%m.%y} ({self.event.time_of_day.name}) - '
            f'{self.event.location_plan_period.location_of_work.name_an_city}')
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
        self.setWindowTitle('Plan-Infos')
        self.appointment = appointment

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
            f'Geben Sie hier die Informationen ein, die für den Termin relevant sind.\n'
            f'Diese werden in die erstellte Excel-Datei des Plans übernommen.\n'
            f'Termin: {self.appointment.event.date:%d.%m.%y} ({self.appointment.event.time_of_day.name}) - '
            f'{self.appointment.event.location_plan_period.location_of_work.name_an_city}')
        self.layout_head.addWidget(self.lb_explanation)
        self.text_info = QTextEdit()
        self.text_info.setText(self.appointment.notes)
        self.bt_reset_from_event = QPushButton('Reset vom Event der Planungsmaske')
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
