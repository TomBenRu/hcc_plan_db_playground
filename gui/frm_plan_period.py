import datetime
from uuid import UUID

from PySide6.QtCore import QDate
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QGridLayout, QLabel, QComboBox, QDateEdit, QPlainTextEdit, QCheckBox, \
    QVBoxLayout, QDialogButtonBox, QMessageBox

from database import db_services, schemas
from gui.tools.qcombobox_find_data import QComboBoxToFindData


class FrmPlanPeriodData(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)

        self.project_id = project_id

        self.setWindowTitle('Planungszeitraum')

        self.max_end_plan_periods: datetime.datetime | None = None

        self.layout = QVBoxLayout()
        self.layout.setSpacing(20)
        self.setLayout(self.layout)

        self.lb_title = QLabel('Erstellen Sie hier einen neuen Planungszeitraum.')
        self.lb_title.setFixedHeight(40)
        self.layout.addWidget(self.lb_title)

        self.data_input_layout = QGridLayout()
        self.data_input_layout.setSpacing(10)
        self.layout.addLayout(self.data_input_layout)

        self.lb_cb_dispatcher = QLabel('Planer*in')
        self.cb_dispatcher = QComboBox()  # wird später über Anmeldeberechtigung bestimmt
        self.cb_dispatcher.currentIndexChanged.connect(self.fill_teams)

        self.lb_cb_teams = QLabel('Team')
        self.cb_teams = QComboBox()
        self.cb_teams.currentIndexChanged.connect(self.fill_dates)

        self.lb_de_start = QLabel('Start')
        self.de_start = QDateEdit()
        self.lb_de_end = QLabel('Ende')
        self.de_end = QDateEdit()
        self.lb_de_deadline = QLabel('Deadline')
        self.de_deadline = QDateEdit()

        self.lb_pt_notes = QLabel('Notizen')
        self.pt_notes = QPlainTextEdit()

        self.chk_remainder = QCheckBox('Remainder verschicken?')

        self.data_input_layout.addWidget(self.lb_cb_dispatcher, 0, 0)
        self.data_input_layout.addWidget(self.cb_dispatcher, 0, 1)
        self.data_input_layout.addWidget(self.lb_cb_teams, 1, 0)
        self.data_input_layout.addWidget(self.cb_teams, 1, 1)
        self.data_input_layout.addWidget(self.lb_de_start, 2, 0)
        self.data_input_layout.addWidget(self.de_start, 2, 1)
        self.data_input_layout.addWidget(self.lb_de_end, 3, 0)
        self.data_input_layout.addWidget(self.de_end)
        self.data_input_layout.addWidget(self.lb_de_deadline, 4, 0)
        self.data_input_layout.addWidget(self.de_deadline, 4, 1)
        self.data_input_layout.addWidget(self.lb_pt_notes, 5, 0)
        self.data_input_layout.addWidget(self.pt_notes, 5, 0, 3, 3)
        self.data_input_layout.addWidget(self.chk_remainder, self.data_input_layout.rowCount(), 0, 1, 2)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.save)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.fill_dispatchers()
        self.fill_dates()

    def fill_teams(self):
        curr_dispatcher: schemas.PersonShow = self.cb_dispatcher.currentData()
        for t in sorted([t for t in curr_dispatcher.teams_of_dispatcher if not t.prep_delete], key=lambda t: t.name):
            self.cb_teams.addItem(QIcon('resources/toolbar_icons/icons/users.png'), t.name, t)

    def fill_dispatchers(self):
        dispatcher = [p for p in db_services.get_persons_of_project(self.project_id)
                      if p.teams_of_dispatcher and not p.prep_delete]
        for d in dispatcher:
            self.cb_dispatcher.addItem(QIcon('resources/toolbar_icons/icons/user.png'), f'{d.f_name} {d.l_name}', d)

    def fill_dates(self):
        team: schemas.TeamShow = self.cb_teams.currentData()
        if team.plan_periods:
            self.max_end_plan_periods = max([p.end for p in team.plan_periods if not p.prep_delete])
        else:
            self.max_end_plan_periods = datetime.date.today()
        self.de_start.setDate(self.max_end_plan_periods + datetime.timedelta(days=1))
        self.de_end.setDate(self.max_end_plan_periods + datetime.timedelta(days=1))
        self.de_deadline.setDate(datetime.date.today())

    def save(self):
        start = self.de_start.date().toPython()
        end = self.de_end.date().toPython()
        deadline = self.de_deadline.date().toPython()

        if start <= self.max_end_plan_periods:
            QMessageBox.critical(self, 'Planungszeitraum',
                                 f'Ihr gewünschter Planungszeitraum überlappt sich mit einem vorhergehenden.\n'
                                 f'Das Startdatum kann frühstens am '
                                 f'{self.max_end_plan_periods + datetime.timedelta(days=1)} sein.')
            return
        if start > end:
            QMessageBox.critical(self, 'Planungszeitraum', 'Das Planungsende darf nicht vor dem Planunganfang sein')
            return
        if not(datetime.date.today() <= deadline <= start):
            QMessageBox.critical(self, 'Planungszeitraum',
                                 'Die Deadline muss sich zwischen einschließlich dem heutigen Datum und dem Beginn des '
                                 'Planungszeitraums befinden.')
            return

        new_plan_period = schemas.PlanPeriodCreate(start=start, end=end, deadline=deadline,
                                                   notes=self.pt_notes.toPlainText(),
                                                   team=self.cb_teams.currentData(),
                                                   remainder=self.chk_remainder.isChecked())
        plan_period_created = db_services.create_planperiod(new_plan_period)
        QMessageBox.information(self, 'Planungszeitraum', f'Planungszeitraum wurde erstellt:\n{plan_period_created}')
        self.accept()


class FrmPlanPeriodCreate(FrmPlanPeriodData):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent, project_id=project_id)


