from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QGridLayout, QLabel, QComboBox, QDateEdit, QPlainTextEdit, QCheckBox

from database import db_services


class PlanPeriodData(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)

        self.setWindowTitle('Planungszeitraum')
        self.dispatchers = db_services.get_persons_of_project(project_id)  # wird später über Anmeldeberechtigung bestimmt

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.lb_cb_dispatcher = QLabel('Planer*in')
        self.cb_dispatcher = QComboBox()
        self.cb_dispatcher.changeEvent(self.fill_teams)

        self.lb_cb_teams = QLabel('Team')
        self.cb_teams = QComboBox()

        self.lb_de_start = QLabel('Start')
        self.de_start = QDateEdit()
        self.lb_de_end = QLabel('Ende')
        self.de_end = QDateEdit()
        self.lb_de_deadline = QLabel('Deadline')
        self.de_deadline = QDateEdit()

        self.lb_pt_notes = QLabel('Notizen')
        self.pt_notes = QPlainTextEdit()

        self.chk_remainder = QCheckBox('Remainder verschicken?')




    def fill_teams(self):
        ...

