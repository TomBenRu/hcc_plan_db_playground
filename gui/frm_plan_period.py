import datetime
from uuid import UUID

from PySide6.QtCore import QDate
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QGridLayout, QLabel, QComboBox, QDateEdit, QPlainTextEdit, QCheckBox, \
    QVBoxLayout, QDialogButtonBox, QMessageBox, QFormLayout

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

        self.data_input_layout = QFormLayout()
        self.data_input_layout.setSpacing(10)
        self.layout.addLayout(self.data_input_layout)

        self.cb_dispatcher = QComboBox()  # wird später über Anmeldeberechtigung bestimmt
        self.cb_dispatcher.currentIndexChanged.connect(self.fill_teams)

        self.cb_teams = QComboBox()
        self.cb_teams.currentIndexChanged.connect(self.fill_dates)

        self.de_start = QDateEdit()
        self.de_end = QDateEdit()
        self.de_deadline = QDateEdit()

        self.pt_notes = QPlainTextEdit()

        self.chk_remainder = QCheckBox('Remainder verschicken?')

        self.data_input_layout.addRow('Planer*in', self.cb_dispatcher)
        self.data_input_layout.addRow('Team', self.cb_teams)
        self.data_input_layout.addRow('Start', self.de_start)
        self.data_input_layout.addRow('Ende', self.de_end)
        self.data_input_layout.addRow('Deadline', self.de_deadline)
        self.data_input_layout.addRow('Notizen', None)
        self.data_input_layout.addRow(self.pt_notes)
        self.data_input_layout.addRow(self.chk_remainder)

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
        if not team:
            return
        if team.plan_periods:
            self.max_end_plan_periods = max([p.end for p in team.plan_periods if not p.prep_delete])
        else:
            self.max_end_plan_periods = datetime.date.today()
        self.de_start.setDate(self.max_end_plan_periods + datetime.timedelta(days=1))
        self.de_end.setDate(self.max_end_plan_periods + datetime.timedelta(days=1))
        self.de_deadline.setDate(datetime.date.today())

    def save(self):
        if not self.cb_teams.currentData():
            QMessageBox.critical(self, 'Planungszeitraum', 'Wie müssen zuerst ein Team auswählen.')
            return
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
        locations = [loc for loc in db_services.get_locations_of_work_of_project(self.project_id)
                     if not loc.prep_delete]
        actors = [p for p in db_services.get_persons_of_project(self.project_id)
                  if p.team_of_actor and not p.prep_delete]
        for loc in locations:
            self.create_location_plan_periods(plan_period_created.id, loc.id)
        for actor in actors:
            self.create_actor_plan_periods(plan_period_created.id, actor.id)

        self.accept()

    def create_location_plan_periods(self, plan_period_id: UUID, loc_id: UUID):
        new_location_plan_period = db_services.create_location_plan_period(plan_period_id, loc_id)
        print(f'{new_location_plan_period=}')
        new_master_event_group = db_services.create_event_group(location_plan_period_id=new_location_plan_period.id)
        print(f'{new_master_event_group=}')

    def create_actor_plan_periods(self, plan_period_id: UUID, person_id: UUID):
        new_actor_plan_period = db_services.create_actor_plan_period(plan_period_id, person_id)
        print(f'{new_actor_plan_period=}')
        new_master_avail_day_group = db_services.create_avail_day_group(actor_plan_period_id=new_actor_plan_period.id)
        print(f'{new_master_avail_day_group=}')


class FrmPlanPeriodCreate(FrmPlanPeriodData):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent, project_id=project_id)
