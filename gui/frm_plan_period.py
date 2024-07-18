import datetime
import os
from uuid import UUID

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QComboBox, QDateEdit, QPlainTextEdit, QCheckBox, \
    QVBoxLayout, QDialogButtonBox, QMessageBox, QFormLayout, QGroupBox, QPushButton

from database import db_services, schemas
from database.special_schema_requests import get_locations_of_team_at_date, \
    get_persons_of_team_at_date
from commands.database_commands import plan_period_commands


class DlgPlanPeriodData(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)

        self.project_id = project_id

        self.setWindowTitle('Planungszeitraum')

        self.max_end_plan_periods: datetime.datetime | None = None

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

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
        self.de_start.dateChanged.connect(self.proof_with_end)
        self.de_end = QDateEdit()
        self.de_end.dateChanged.connect(self.proof_with_start)
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
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

        self.fill_dispatchers()
        self.fill_dates()

    def fill_teams(self):
        curr_dispatcher: schemas.PersonShow = self.cb_dispatcher.currentData()
        for t in sorted([t for t in curr_dispatcher.teams_of_dispatcher if not t.prep_delete], key=lambda t: t.name):
            team = db_services.Team.get(t.id)
            self.cb_teams.addItem(QIcon(os.path.join(self.path_to_icons, 'resources/toolbar_icons/icons/users.png')), team.name, team)

    def fill_dispatchers(self):
        dispatcher = [p for p in db_services.Person.get_all_from__project(self.project_id)
                      if p.teams_of_dispatcher and not p.prep_delete]
        for d in dispatcher:
            self.cb_dispatcher.addItem(QIcon(os.path.join(self.path_to_icons, 'resources/toolbar_icons/icons/user.png')), f'{d.f_name} {d.l_name}', d)

    def fill_dates(self):
        team: schemas.TeamShow = self.cb_teams.currentData()
        if not team:
            return
        if plan_periods := [pp for pp in team.plan_periods if not pp.prep_delete]:
            self.max_end_plan_periods = max(p.end for p in plan_periods)
        else:
            self.max_end_plan_periods = datetime.date.today()
        self.de_start.setMinimumDate(self.max_end_plan_periods + datetime.timedelta(days=1))
        self.de_end.setMinimumDate(self.max_end_plan_periods + datetime.timedelta(days=1))
        self.de_start.setDate(self.max_end_plan_periods + datetime.timedelta(days=1))
        self.de_end.setDate(self.max_end_plan_periods + datetime.timedelta(days=1))
        self.de_deadline.setDate(datetime.date.today())

    def proof_with_end(self):
        if self.de_start.date() > self.de_end.date():
            self.de_end.setDate(self.de_start.date())

    def proof_with_start(self):
        if self.de_end.date() < self.de_start.date():
            self.de_start.setDate(self.de_end.date())

    def get_locations_actors_in_period(self, start: datetime.date, end: datetime.date) -> tuple[set[UUID], set[UUID]]:
        """Gibt ein Tuple von Sets zurück: location_ids, actor_ids"""
        location_ids = set()
        actor_ids = set()
        for delta in range((end - start).days + 1):
            location_ids |= {
                loc.id for loc in
                get_locations_of_team_at_date(self.cb_teams.currentData().id, start + datetime.timedelta(days=delta))}
            actor_ids |= {
                pers.id for pers in
                get_persons_of_team_at_date(self.cb_teams.currentData().id, start + datetime.timedelta(days=delta))}
        return location_ids, actor_ids

    def accept(self) -> None:
        if not self.cb_teams.currentData():
            QMessageBox.critical(self, 'Planungszeitraum', 'Wie müssen zuerst ein Team auswählen.')
            return
        start = self.de_start.date().toPython()
        end = self.de_end.date().toPython()
        deadline = self.de_deadline.date().toPython()

        new_plan_period = schemas.PlanPeriodCreate(start=start, end=end, deadline=deadline,
                                                   notes=self.pt_notes.toPlainText(),
                                                   team=self.cb_teams.currentData(),
                                                   remainder=self.chk_remainder.isChecked())
        plan_period_created = db_services.PlanPeriod.create(new_plan_period)

        location_ids, actor_ids = self.get_locations_actors_in_period(start, end)

        for loc_id in location_ids:
            self.create_location_plan_periods(plan_period_created.id, loc_id)
        for actor_id in actor_ids:
            self.create_actor_plan_periods(plan_period_created.id, actor_id)

        super().accept()

    def create_location_plan_periods(self, plan_period_id: UUID, loc_id: UUID):
        new_location_plan_period = db_services.LocationPlanPeriod.create(plan_period_id, loc_id)
        new_master_event_group = db_services.EventGroup.create(location_plan_period_id=new_location_plan_period.id)

    def create_actor_plan_periods(self, plan_period_id: UUID, person_id: UUID):
        new_actor_plan_period = db_services.ActorPlanPeriod.create(plan_period_id, person_id)
        new_master_avail_day_group = db_services.AvailDayGroup.create(actor_plan_period_id=new_actor_plan_period.id)


class DlgPlanPeriodCreate(DlgPlanPeriodData):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent, project_id=project_id)


class DlgPlanPeriodEdit(QDialog):
    # todo: Änderungen abspeichern
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)

        self.setWindowTitle('Planung ändern')

        self.project_id = project_id
        self.curr_plan_periods: list[schemas.PlanPeriod] = []

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.layout.setSpacing(20)

        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_explanation = QLabel('Ändern Sie hier eine bestehende Planung.')
        self.layout_head.addWidget(self.lb_explanation)

        self.group_pp_select = QGroupBox('Auswahl Planung')
        self.group_pp_datas = QGroupBox('Planungsdaten')
        self.layout_body.addWidget(self.group_pp_select)
        self.layout_body.addWidget(self.group_pp_datas)

        self.layout_pp_select = QFormLayout(self.group_pp_select)
        self.layout_pp_datas = QFormLayout(self.group_pp_datas)

        self.cb_dispatcher = QComboBox()
        self.cb_dispatcher.currentIndexChanged.connect(self.fill_teams)
        self.cb_teams = QComboBox()
        self.cb_teams.currentIndexChanged.connect(self.fill_plan_periods)
        self.cb_planperiods = QComboBox()
        self.cb_planperiods.currentIndexChanged.connect(self.fill_plan_period_datas)

        self.layout_pp_select.addRow('Auswahl Planer*in:', self.cb_dispatcher)
        self.layout_pp_select.addRow('Auswahl Team:', self.cb_teams)
        self.layout_pp_select.addRow('Aúswahl Planung:', self.cb_planperiods)

        self.de_start = QDateEdit()
        self.de_start.dateChanged.connect(self.proof_with_end)
        self.de_end = QDateEdit()
        self.de_end.dateChanged.connect(self.proof_with_start)
        self.de_deadline = QDateEdit()
        self.te_notes = QPlainTextEdit()
        self.chk_remainder = QCheckBox('Remainder verschicken')

        self.layout_pp_datas.addRow('Start:', self.de_start)
        self.layout_pp_datas.addRow('Ende:', self.de_end)
        self.layout_pp_datas.addRow('Deadline:', self.de_deadline)
        self.layout_pp_datas.addRow('Notizen:', None)
        self.layout_pp_datas.addRow(self.te_notes)
        self.layout_pp_datas.addRow(self.chk_remainder)

        self.bt_delete = QPushButton('Delete')
        self.bt_delete.clicked.connect(self.delete)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.addButton(self.bt_delete, QDialogButtonBox.ButtonRole.ActionRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

        self.fill_dispatchers()

    def fill_dispatchers(self):
        dispatcher = [p for p in db_services.Person.get_all_from__project(self.project_id)
                      if p.teams_of_dispatcher and not p.prep_delete]
        for d in dispatcher:
            self.cb_dispatcher.addItem(QIcon(os.path.join(self.path_to_icons, 'resources/toolbar_icons/icons/user.png')), f'{d.f_name} {d.l_name}', d)

    def fill_teams(self):
        self.cb_teams.clear()
        curr_dispatcher: schemas.PersonShow = self.cb_dispatcher.currentData()
        for t in sorted([t for t in curr_dispatcher.teams_of_dispatcher if not t.prep_delete], key=lambda t: t.name):
            team = db_services.Team.get(t.id)
            self.cb_teams.addItem(QIcon(os.path.join(self.path_to_icons, 'resources/toolbar_icons/icons/users.png')), team.name, team)

    def fill_plan_periods(self):
        self.cb_planperiods.clear()
        curr_team: schemas.TeamShow = self.cb_teams.currentData()
        self.curr_plan_periods = sorted([p for p in curr_team.plan_periods if not p.prep_delete],
                                        key=lambda x: x.start, reverse=True)
        for pp in self.curr_plan_periods:
            text = f'{pp.start.strftime("%d.%m.%Y")} - {pp.end.strftime("%d.%m.%Y")}'
            self.cb_planperiods.addItem(text, pp)

    def fill_plan_period_datas(self):
        pp_after = (self.curr_plan_periods[self.cb_planperiods.currentIndex() - 1]
                    if self.cb_planperiods.currentIndex() > 0 else None)
        pp_before = (self.curr_plan_periods[self.cb_planperiods.currentIndex() + 1]
                     if len(self.curr_plan_periods) > (self.cb_planperiods.currentIndex() + 1) else None)

        self.de_start.clearMinimumDate()
        self.de_end.clearMaximumDate()
        if plan_period := self.cb_planperiods.currentData():
            self.disable_enable_data_fields(False)
            self.de_start.setDate(plan_period.start)
            if pp_before:
                self.de_start.setMinimumDate(pp_before.end + datetime.timedelta(days=1))
            self.de_end.setDate(plan_period.end)
            if pp_after:
                self.de_end.setMaximumDate(pp_after.start - datetime.timedelta(days=1))
            self.de_deadline.setDate(plan_period.deadline)
            self.te_notes.setPlainText(plan_period.notes)
            self.chk_remainder.setChecked(plan_period.remainder)
        else:
            self.de_start.setDate(datetime.date(year=1999, month=1, day=1))
            self.de_end.setDate(datetime.date(year=1999, month=1, day=1))
            self.de_deadline.setDate(datetime.date(year=1999, month=1, day=1))
            self.te_notes.clear()
            self.chk_remainder.setChecked(False)
            self.disable_enable_data_fields(True)

    def disable_enable_data_fields(self, disable: bool):
        self.de_start.setDisabled(disable)
        self.de_end.setDisabled(disable)
        self.de_deadline.setDisabled(disable)
        self.te_notes.setDisabled(disable)
        self.chk_remainder.setDisabled(disable)

    def proof_with_end(self):
        if self.de_start.date() > self.de_end.date():
            self.de_end.setDate(self.de_start.date())

    def proof_with_start(self):
        if self.de_end.date() < self.de_start.date():
            self.de_start.setDate(self.de_end.date())

    def delete(self):
        reply = QMessageBox.question(self, 'Planungsperiode löschen',
                                     'Wollen Sie diese Planungsperiode wirklich löschen?')
        print(f'{reply=}')
        if reply == QMessageBox.StandardButton.Yes:
            print('accepted')
            plan_period_commands.Delete(self.cb_planperiods.currentData().id).execute()
            self.accept()
