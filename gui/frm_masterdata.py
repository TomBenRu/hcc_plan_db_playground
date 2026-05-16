import datetime
import functools
import os
import webbrowser
from functools import partial
from typing import TYPE_CHECKING
from uuid import UUID

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QMessageBox, QLineEdit, QComboBox, \
    QGroupBox, QPushButton, QDialogButtonBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHBoxLayout, QSpinBox, \
    QFormLayout, QHeaderView, QMainWindow

from gui.frm_skill_groups import DlgSkillGroups
from gui.api_client.client import get_api_client
from database import db_services, schemas
from database.enums import Gender
from database.special_schema_requests import get_curr_team_of_person_at_date, \
    get_curr_team_of_location_at_date, get_next_assignment_of_location
from gui import frm_time_of_day, frm_comb_loc_possible, frm_actor_loc_prefs, frm_partner_location_prefs, \
    frm_skills
from commands import command_base_classes
from commands.database_commands import person_commands, location_of_work_commands, \
    actor_partner_loc_pref_commands
from tools.helper_functions import date_to_string, setup_form_help
from .frm_fixed_cast import DlgFixedCastBuilderLocationOfWork
from gui.custom_widgets.tabbars import TabBar

if TYPE_CHECKING:
    from .main_window import MainWindow


class FrmMasterData(QMainWindow):
    def __init__(self, parent: 'MainWindow', project_id: UUID):
        super().__init__(parent)
        
        # Help-System Integration
        setup_form_help(self, "masterdata", add_help_button=True, help_button_style='floating')
        
        self.setWindowTitle(self.tr('Master Data'))
        self.setGeometry(50, 50, 1000, 600)

        self.project_id = project_id

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.tab_bar = TabBar(self.central_widget, 'north', 12, 20, 200, False, False,
                              None, 'tabbar_masterdata')

        self.widget_persons = WidgetPerson(project_id)

        self.widget_locations_of_work = WidgetLocationsOfWork(project_id)

        self.tab_bar.addTab(self.widget_persons, self.tr('Employees'))
        self.tab_bar.addTab(self.widget_locations_of_work, self.tr('Facilities'))
        self.layout.addWidget(self.tab_bar)


class WidgetPerson(QWidget):
    def __init__(self, project_id: UUID):
        super().__init__()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout_buttons = QHBoxLayout()
        self.layout_buttons.setAlignment(Qt.AlignLeft)
        self.layout.addLayout(self.layout_buttons)

        self.project_id = project_id

        self.persons = self.get_persons()

        self.table_persons = TablePersons(self.persons, self.project_id)
        self.table_persons.cellDoubleClicked.connect(self.edit_person)

        self.layout.addWidget(self.table_persons)

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.bt_edit = QPushButton(QIcon(os.path.join(self.path_to_icons, 'user--pencil.png')), self.tr('Edit Person'))
        self.bt_edit.setFixedWidth(200)
        self.bt_edit.clicked.connect(self.edit_person)

        self.layout_buttons.addWidget(self.bt_edit)

    def get_persons(self) -> list[schemas.PersonForMasterData]:
        try:
            return db_services.Person.get_all_for_master_data_table(self.project_id)
        except Exception as e:
            QMessageBox.critical(self, self.tr('Error'), self.tr('Error: {}').format(e))

    def refresh_table(self):
        self.persons = self.get_persons()
        self.table_persons.persons = self.persons
        self.table_persons.clearContents()
        self.table_persons.setSortingEnabled(False)
        self.table_persons.put_data_to_table()
        self.table_persons.setSortingEnabled(True)

    def edit_person(self):
        row = self.table_persons.currentRow()
        if row == -1:
            QMessageBox.information(self, self.tr('Edit'),
                                  self.tr('Please select an entry first.\nClick on the corresponding row.'))
            return
        person = db_services.Person.get(self.table_persons.item(row, 0).data(Qt.ItemDataRole.UserRole))
        dlg = DlgPersonModify(self, self.project_id, person)
        if dlg.exec():
            self.refresh_table()


class TablePersons(QTableWidget):
    def __init__(self, persons: list[schemas.PersonShow], project_id: UUID, sorting_column: int = 0):
        super().__init__()

        self.persons = persons
        self.project_id = project_id

        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.headers = [
            self.tr('First Name'),
            self.tr('Last Name'),
            self.tr('Email'),
            self.tr('Gender'),
            self.tr('Phone'),
            self.tr('Street'),
            self.tr('ZIP'),
            self.tr('City'),
            self.tr('Team'),
        ]
        self.setColumnCount(len(self.headers))
        self.setColumnWidth(6, 50)
        self.setHorizontalHeaderLabels(self.headers)
        self.gender_visible_strings = {
            'm': self.tr('male'),
            'f': self.tr('female'),
            'd': self.tr('diverse')
        }

        self.put_data_to_table()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

        # sort table by first name
        self.sortItems(sorting_column, Qt.SortOrder.AscendingOrder)

    def put_data_to_table(self):
        # Sortierung temporär deaktivieren, um Daten-Mismatch zu vermeiden
        self.setSortingEnabled(False)

        today = datetime.date.today()
        person_ids = [p.id for p in self.persons]
        teams_by_person = db_services.TeamActorAssign.get_team_names_for_persons_at_date(
            person_ids, today)

        self.setRowCount(len(self.persons))
        for row, p in enumerate(self.persons):
            item_f_name = QTableWidgetItem(p.f_name)
            item_f_name.setData(Qt.ItemDataRole.UserRole, p.id)
            self.setItem(row, 0, item_f_name)
            self.setItem(row, 1, QTableWidgetItem(p.l_name))
            self.setItem(row, 2, QTableWidgetItem(p.email))
            self.setItem(row, 3, QTableWidgetItem(
                self.gender_visible_strings[p.gender.value] if p.gender else ''))
            self.setItem(row, 4, QTableWidgetItem(p.phone_nr))
            self.setItem(row, 5, QTableWidgetItem(p.address.street if p.address else ''))
            self.setItem(row, 6, QTableWidgetItem(p.address.postal_code if p.address else ''))
            self.setItem(row, 7, QTableWidgetItem(p.address.city if p.address else ''))

            # Team-Spalte: Komma-separierte Team-Namen der Person (heute).
            # Bearbeitung der Team-Zuordnungen erfolgt im Web-UI unter /admin/teams.
            names = teams_by_person.get(p.id, [])
            team_names = ', '.join(names) if names else self.tr('No Team')
            item_teams = QTableWidgetItem(team_names)
            item_teams.setToolTip(team_names if names else '')
            self.setItem(row, 8, item_teams)

        # Sortierung wieder aktivieren
        self.setSortingEnabled(True)

    def refresh_table(self):
        """Aktualisiert die gesamte Tabelle mit aktuellen Daten."""
        self.persons = db_services.Person.get_batch([p.id for p in self.persons])
        self.put_data_to_table()


class DlgPersonData(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)

        self.setWindowTitle(self.tr('Person Data'))

        self.project_id = project_id
        self.project = db_services.Project.get(project_id)

        self._setup_ui()

    def _setup_ui(self):
        self.setMinimumWidth(350)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.group_person_data = QGroupBox(self.tr('Personal Data'))
        self.group_person_data_layout = QFormLayout(self.group_person_data)
        self.layout.addWidget(self.group_person_data)

        self.group_address_data = QGroupBox(self.tr('Address Data'))
        self.group_address_data_layout = QFormLayout(self.group_address_data)
        self.layout.addWidget(self.group_address_data)

        self.le_f_name = QLineEdit()
        self.le_l_name = QLineEdit()
        self.le_email = QLineEdit()
        self.cb_gender = QComboBox()
        self.cb_gender.addItems([n.name for n in Gender])
        self.le_phone_nr = QLineEdit()
        self.le_street = QLineEdit()
        self.le_postal_code = QLineEdit()
        self.le_city = QLineEdit()
        self.le_descriptive_name = QLineEdit()
        self.le_descriptive_name.setPlaceholderText(self.tr('Optional, e.g. "John Doe"'))

        # Stammdaten werden im Web unter /admin/teams gepflegt — Anzeige read-only.
        for w in (self.le_f_name, self.le_l_name, self.le_email, self.le_phone_nr,
                  self.le_street, self.le_postal_code, self.le_city, self.le_descriptive_name):
            w.setReadOnly(True)
        self.cb_gender.setEnabled(False)

        self.group_person_data_layout.addRow(self.tr('First Name'), self.le_f_name)
        self.group_person_data_layout.addRow(self.tr('Last Name'), self.le_l_name)
        self.group_person_data_layout.addRow(self.tr('Email'), self.le_email)
        self.group_person_data_layout.addRow(self.tr('Gender'), self.cb_gender)
        self.group_person_data_layout.addRow(self.tr('Phone'), self.le_phone_nr)
        self.group_address_data_layout.addRow(self.tr('Street'), self.le_street)
        self.group_address_data_layout.addRow(self.tr('ZIP'), self.le_postal_code)
        self.group_address_data_layout.addRow(self.tr('City'), self.le_city)
        self.group_address_data_layout.addRow(self.tr('Descriptive Name'), self.le_descriptive_name)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)


class DlgPersonModify(DlgPersonData):
    def __init__(self, parent: QWidget, project_id: UUID, person: schemas.PersonShow):
        self.project_id = project_id
        self.person = person
        self.controller = command_base_classes.ContrExecUndoRedo()

        super().__init__(parent, project_id)


    def _setup_ui(self):
        super()._setup_ui()
        self.group_specific_data = QGroupBox(self.tr('Specific Data'))
        self.group_specific_data_layout = QFormLayout(self.group_specific_data)
        self.layout.addWidget(self.group_specific_data)

        self.le_id = QLineEdit()
        self.le_id.setReadOnly(True)
        self.spin_num_requested_assignments = QSpinBox()
        self.spin_num_requested_assignments.setMinimum(0)
        self.bt_time_of_days = QPushButton(self.tr('Edit...'), clicked=self.edit_time_of_days)
        self.bt_comb_loc_possible = QPushButton(self.tr('Edit...'), clicked=self.edit_comb_loc_possible)
        self.bt_actor_loc_prefs = QPushButton(self.tr('Edit...'), clicked=self.edit_location_prefs)
        self.bt_actor_partner_loc_prefs = QPushButton(self.tr('Edit...'),
                                                      clicked=self.edit_partner_location_prefs)
        self.bt_skills = QPushButton(self.tr('Edit...'), clicked=self.select_skills)

        self.group_person_data_layout.addRow(self.tr('ID'), self.le_id)
        self.group_specific_data_layout.addRow(self.tr('Requested Assignments'), self.spin_num_requested_assignments)
        self.group_specific_data_layout.addRow(self.tr('Times of Day'), self.bt_time_of_days)
        self.group_specific_data_layout.addRow(self.tr('Location Combinations'), self.bt_comb_loc_possible)
        self.group_specific_data_layout.addRow(self.tr('Location Preferences'), self.bt_actor_loc_prefs)
        self.group_specific_data_layout.addRow(self.tr('Employee Preferences'), self.bt_actor_partner_loc_prefs)
        self.group_specific_data_layout.addRow(self.tr('Skills'), self.bt_skills)

        self.bt_edit_in_web = QPushButton(self.tr('Stammdaten im Web bearbeiten…'),
                                          clicked=self._open_in_web)
        self.group_person_data_layout.addRow('', self.bt_edit_in_web)

        self.layout.addWidget(self.button_box)
        self.button_box.rejected.connect(self.reject)
        self.autofill()

    def _open_in_web(self):
        webbrowser.open(f"{get_api_client().base_url}/admin/teams")

    def accept(self):
        # Stammdaten (Name, Email, Gender, Phone, Adresse) sind seit Schicht-B
        # read-only — Bearbeitung erfolgt im Web /admin/teams. Hier nur noch
        # die Plan-Konfig-Felder schreiben.
        self.person.requested_assignments = self.spin_num_requested_assignments.value()
        update_person_command = person_commands.Update(self.person)
        self.controller.execute(update_person_command)
        updated_person = update_person_command.updated_person
        QMessageBox.information(self, self.tr('Person Update'),
                                self.tr('Person has been updated:\n{} {}').format(
                                    updated_person.f_name, updated_person.l_name))
        super().accept()

    def reject(self):
        self.controller.undo_all()
        super().reject()

    def autofill(self):
        self.fill_person_data()
        self.fill_address_data()
        self.fill_requested_assignm()

    def fill_person_data(self):
        self.le_id.setText(str(self.person.id))
        self.le_f_name.setText(self.person.f_name)
        self.le_l_name.setText(self.person.l_name)
        self.le_email.setText(self.person.email)
        self.cb_gender.setCurrentText(self.person.gender.name if self.person.gender else 'divers')
        self.le_phone_nr.setText(self.person.phone_nr)

    def fill_address_data(self):
        if not self.person.address:
            return
        self.le_street.setText(self.person.address.street)
        self.le_postal_code.setText(self.person.address.postal_code)
        self.le_city.setText(self.person.address.city)
        self.le_descriptive_name.setText(self.person.address.name or '')

    def fill_requested_assignm(self):
        self.spin_num_requested_assignments.setValue(self.person.requested_assignments)

    def edit_time_of_days(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderPerson(self, self.person).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.person = db_services.Person.get(self.person.id)

    def edit_comb_loc_possible(self):
        team_at_date_factory = parent_model_factory = partial(get_curr_team_of_person_at_date, self.person)

        dlg = frm_comb_loc_possible.DlgCombLocPossibleEditList(self, self.person, parent_model_factory,
                                                               team_at_date_factory)
        if dlg.exec():
            self.controller.execute(
                person_commands.ReplaceCombLocPossibles(
                    person_id=self.person.id,
                    original_ids=dlg.original_ids,
                    pending_creates=dlg.pending_creates,
                    current_combs=list(dlg.curr_model.combination_locations_possibles),
                )
            )
            self.person = db_services.Person.get(self.person.id)

    def edit_location_prefs(self):

        team_at_date_factory = functools.partial(get_curr_team_of_person_at_date, self.person)

        dlg = frm_actor_loc_prefs.DlgActorLocPref(self, self.person, None, team_at_date_factory)
        if not dlg.exec():
            return
        self.controller.execute(
            person_commands.UpdateLocationPrefsBulk(
                self.person.id, self.person.project.id, dlg.loc_id__results
            )
        )
        self.person = db_services.Person.get(self.person.id)

    def edit_partner_location_prefs(self):
        team = get_curr_team_of_person_at_date(self.person)
        if not team:
            QMessageBox.critical(self, self.tr('Employee Preferences'),
                                 self.tr('{} {} is not yet a member of any team').format(
                                     self.person.f_name, self.person.l_name))
            return

        team_at_date_factory = partial(get_curr_team_of_person_at_date, self.person)

        dlg = frm_partner_location_prefs.DlgPartnerLocationPrefs(self, self.person, self.person, None,
                                                                 team_at_date_factory)
        if not dlg.exec():
            return
        self.controller.execute(
            actor_partner_loc_pref_commands.ReplaceAll(
                model_class_name=self.person.__class__.__name__,
                model_id=self.person.id,
                person_id=self.person.id,
                new_prefs=dlg.new_prefs,
            )
        )
        self.person = db_services.Person.get(self.person.id)

    def select_skills(self):
        dlg = frm_skills.DlgSelectSkills(self, self.person)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.person = db_services.Person.get(self.person.id)
        else:
            dlg.controller.undo_all()


class WidgetLocationsOfWork(QWidget):
    def __init__(self, project_id: UUID):
        super().__init__()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout_buttons = QHBoxLayout()
        self.layout_buttons.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.addLayout(self.layout_buttons)

        self.project_id = project_id

        self.locations = self.get_locations()

        self.table_locations = TableLocationsOfWork(self.locations)
        self.table_locations.cellDoubleClicked.connect(self.edit_location)
        self.layout.addWidget(self.table_locations)

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.bt_edit = QPushButton(QIcon(os.path.join(self.path_to_icons, 'store--pencil.png')), ' ' + self.tr('Edit Facility'))
        self.bt_edit.setFixedWidth(200)
        self.bt_edit.clicked.connect(self.edit_location)

        self.layout_buttons.addWidget(self.bt_edit)

    def get_locations(self) -> list[schemas.LocationOfWorkShow]:
        return db_services.LocationOfWork.get_all_from__project(self.project_id)

    def refresh_table(self):
        self.locations = self.get_locations()
        self.table_locations.locations = self.locations
        self.table_locations.clearContents()
        self.table_locations.setSortingEnabled(False)
        self.table_locations.put_data_to_table()
        self.table_locations.setSortingEnabled(True)

    def edit_location(self):
        row = self.table_locations.currentRow()
        if row == -1:
            QMessageBox.information(self, self.tr('Edit'),
                                  self.tr('You must first select an entry.\n'
                                        'Click on the corresponding row.'))
            return
        location_id = self.table_locations.item(row, 0).data(Qt.ItemDataRole.UserRole)
        dlg = DlgLocationModify(self, self.project_id, location_id)
        if dlg.exec():
            self.refresh_table()


class TableLocationsOfWork(QTableWidget):
    def __init__(self, locations: list[schemas.LocationOfWorkShow]):
        super().__init__()

        self.locations = locations

        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.horizontalHeader().setHighlightSections(False)
        self.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        # Using tr() for column headers
        self.headers = [
            self.tr('Name'),
            self.tr('Street'),
            self.tr('ZIP'),
            self.tr('City'),
            self.tr('Team'),
            self.tr('Staff')
        ]
        self.setColumnCount(len(self.headers))
        self.setColumnWidth(4, 50)
        self.setHorizontalHeaderLabels(self.headers)

        self.put_data_to_table()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def put_data_to_table(self):
        self.setRowCount(len(self.locations))
        for row, loc in enumerate(self.locations):
            item_name = QTableWidgetItem(loc.name)
            item_name.setData(Qt.ItemDataRole.UserRole, loc.id)
            self.setItem(row, 0, item_name)
            self.setItem(row, 1, QTableWidgetItem(loc.address.street if loc.address else ''))
            self.setItem(row, 2, QTableWidgetItem(loc.address.postal_code if loc.address else ''))
            self.setItem(row, 3, QTableWidgetItem(loc.address.city if loc.address else ''))

            curr_team = get_curr_team_of_location_at_date(location=loc)
            txt_team = self.get_team_info_text(loc, curr_team)
            self.setItem(row, 4, QTableWidgetItem(txt_team))
            self.setItem(row, 5, QTableWidgetItem(str(loc.nr_actors)))

    @staticmethod
    def get_team_info_text(location: schemas.LocationOfWorkShow, curr_team: schemas.Team | None) -> str:
        if curr_team:
            return curr_team.name
        if next_assignment__date := get_next_assignment_of_location(location, datetime.date.today()):
            next_assignment, date = next_assignment__date
            if next_assignment:
                return QCoreApplication.translate("TableLocationsOfWork",
                    "{team} from {date}").format(
                        team=(next_assignment.team.name if next_assignment
                              else QCoreApplication.translate("TableLocationsOfWork", "No Team")),
                        date=date_to_string(date))
        return ''


class DlgLocationData(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)

        self.setMinimumWidth(350)

        self.project_id = project_id
        self.project = db_services.Project.get(project_id)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.group_location_data = QGroupBox(self.tr('Facility Data'))
        self.group_location_data_layout = QFormLayout(self.group_location_data)
        self.layout.addWidget(self.group_location_data)
        self.group_address_data = QGroupBox(self.tr('Address Data'))
        self.group_address_data_layout = QFormLayout(self.group_address_data)
        self.layout.addWidget(self.group_address_data)

        self.le_name = QLineEdit()
        self.le_street = QLineEdit()
        self.le_postal_code = QLineEdit()
        self.le_city = QLineEdit()
        self.le_descriptive_name = QLineEdit()
        self.le_descriptive_name.setPlaceholderText(self.tr('Optional, e.g. "Clinic XYZ"'))

        # Stammdaten werden im Web unter /admin/teams gepflegt — Anzeige read-only.
        for w in (self.le_name, self.le_street, self.le_postal_code,
                  self.le_city, self.le_descriptive_name):
            w.setReadOnly(True)

        self.group_location_data_layout.addRow(self.tr('Name'), self.le_name)
        self.group_address_data_layout.addRow(self.tr('Street'), self.le_street)
        self.group_address_data_layout.addRow(self.tr('ZIP Code'), self.le_postal_code)
        self.group_address_data_layout.addRow(self.tr('City'), self.le_city)
        self.group_address_data_layout.addRow(self.tr('Descriptive Name'), self.le_descriptive_name)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)


class DlgLocationModify(DlgLocationData):
    def __init__(self, parent: QWidget, project_id: UUID, location_id: UUID):
        super().__init__(parent, project_id=project_id)

        self.setWindowTitle(self.tr('Facility Data'))
        self.location_id = location_id
        self.controller = command_base_classes.ContrExecUndoRedo()
        self.location_of_work = self.get_location_of_work()
        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.button_box.accepted.connect(self.save_location)
        self.button_box.rejected.connect(self.reject)

        self._setup_ui()
        self._autofill_widgets()

    def _setup_ui(self):
        self.group_specific_data = QGroupBox(self.tr('Specific Data'))
        self.layout_group_specific_data = QFormLayout(self.group_specific_data)
        self.layout.addWidget(self.group_specific_data)

        self.le_id = QLineEdit()
        self.le_id.setReadOnly(True)
        self.spin_nr_actors = QSpinBox()
        self.spin_nr_actors.setMinimum(1)
        self.bt_time_of_days = QPushButton(self.tr('Edit...'), clicked=self.edit_time_of_days)
        self.bt_fixed_cast = QPushButton(self.tr('Edit...'), clicked=self.edit_fixed_cast)
        self.bt_skill_groups = QPushButton(self.tr('Edit...'), clicked=self.edit_skill_groups)
        self.bt_edit_in_web = QPushButton(self.tr('Stammdaten im Web bearbeiten…'),
                                          clicked=self._open_in_web)

        self.group_location_data_layout.addRow(self.tr('ID'), self.le_id)
        self.group_location_data_layout.addRow('', self.bt_edit_in_web)
        self.layout_group_specific_data.addRow(self.tr('Staff Count'), self.spin_nr_actors)
        self.layout_group_specific_data.addRow(self.tr('Times of Day'), self.bt_time_of_days)
        self.layout_group_specific_data.addRow(self.tr('Desired Staff'), self.bt_fixed_cast)
        self.layout_group_specific_data.addRow(self.tr('Skill Groups'), self.bt_skill_groups)
        self.layout.addWidget(self.button_box)

    def _open_in_web(self):
        webbrowser.open(f"{get_api_client().base_url}/admin/teams?tab=locations")

    def _autofill_widgets(self):
        self.le_name.setText(self.location_of_work.name)
        self.le_id.setText(str(self.location_of_work.id))
        if self.location_of_work.address:
            self.le_street.setText(self.location_of_work.address.street)
            self.le_postal_code.setText(self.location_of_work.address.postal_code)
            self.le_city.setText(self.location_of_work.address.city)
            self.le_descriptive_name.setText(self.location_of_work.address.name or '')
        self.spin_nr_actors.setValue(self.location_of_work.nr_actors)

    def save_location(self):
        # Stammdaten (Name, Adresse) und Team-Mitgliedschaft sind seit Schicht-B
        # read-only — Bearbeitung erfolgt im Web /admin/teams. Hier nur noch die
        # Plan-Konfig-Felder schreiben.
        self.location_of_work.nr_actors = self.spin_nr_actors.value()
        update_location_command = location_of_work_commands.Update(self.location_of_work)
        self.controller.execute(update_location_command)
        updated_location = update_location_command.updated_location_of_work
        QMessageBox.information(self, self.tr('Location Update'),
                              self.tr('The location has been updated:\n{name}').format(
                                  name=updated_location.name))
        self.accept()

    def reject(self):
        self.controller.undo_all()
        super().reject()

    def get_location_of_work(self):
        return db_services.LocationOfWork.get(self.location_id)

    def edit_time_of_days(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderLocation(self, self.location_of_work).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.location_of_work = db_services.LocationOfWork.get(self.location_of_work.id)

    def edit_fixed_cast(self):
        dlg = DlgFixedCastBuilderLocationOfWork(self, self.location_of_work).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.location_of_work = db_services.LocationOfWork.get(self.location_of_work.id)

    def edit_skill_groups(self):
        dlg = DlgSkillGroups(self, self.location_of_work)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.location_of_work = self.get_location_of_work()
        else:
            dlg.controller.undo_all()
