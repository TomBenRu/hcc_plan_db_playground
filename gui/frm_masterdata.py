import datetime
import functools
import os
from functools import partial
from typing import TYPE_CHECKING
from uuid import UUID

from PySide6.QtCore import Qt, QCoreApplication
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QMessageBox, QLabel, QLineEdit, QComboBox, \
    QGroupBox, QPushButton, QDialogButtonBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHBoxLayout, QSpinBox, \
    QFormLayout, QHeaderView, QFileDialog, QMainWindow

from gui.frm_skill_groups import DlgSkillGroups
from database import db_services, schemas
from database.enums import Gender
from database.special_schema_requests import get_curr_team_of_person_at_date, \
    get_curr_team_of_location_at_date, get_next_assignment_of_location
from gui import frm_time_of_day, frm_comb_loc_possible, frm_actor_loc_prefs, frm_partner_location_prefs, \
    frm_assign_to_team, frm_skills, frm_team_assignments
from commands import command_base_classes
from commands.database_commands import person_commands, location_of_work_commands, \
    location_plan_period_commands, event_group_commands, address_commands, actor_partner_loc_pref_commands
from gui.api_client.client import ApiError
from tools.helper_functions import date_to_string, setup_form_help
from .frm_fixed_cast import DlgFixedCastBuilderLocationOfWork
from gui.custom_widgets.tabbars import TabBar
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData

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

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.persons = self.get_persons()

        self.table_persons = TablePersons(self.persons, self.project_id)
        self.table_persons.cellDoubleClicked.connect(self.edit_person)

        self.layout.addWidget(self.table_persons)

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.bt_new = QPushButton(QIcon(os.path.join(self.path_to_icons, 'user--plus.png')), self.tr('Create Person'))
        self.bt_new.setFixedWidth(200)
        self.bt_new.clicked.connect(self.create_person)

        self.bt_new_from_xlsx = QPushButton(QIcon(os.path.join(self.path_to_icons, 'file--plus.png')), self.tr('Import People from XLSX'))
        self.bt_new_from_xlsx.setFixedWidth(200)
        self.bt_new_from_xlsx.clicked.connect(self.create_persons_from_xlsx)
        self.bt_new_from_xlsx.setToolTip(self.tr('Import employees from XLSX file.\nColumns: First name, Last name, username'))

        self.bt_edit = QPushButton(QIcon(os.path.join(self.path_to_icons, 'user--pencil.png')), self.tr('Edit Person'))
        self.bt_edit.setFixedWidth(200)
        self.bt_edit.clicked.connect(self.edit_person)

        self.bt_delete = QPushButton(QIcon(os.path.join(self.path_to_icons, 'user--minus.png')), self.tr('Delete Person'))
        self.bt_delete.setFixedWidth(200)
        self.bt_delete.clicked.connect(self.delete_person)

        self.layout_buttons.addWidget(self.bt_new)
        self.layout_buttons.addWidget(self.bt_new_from_xlsx)
        self.layout_buttons.addWidget(self.bt_edit)
        self.layout_buttons.addWidget(self.bt_delete)

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

    def create_person(self):
        dlg = DlgPersonCreate(self, self.project_id)
        if dlg.exec():
            self.refresh_table()
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())

    def create_persons_from_xlsx(self):
        """
        Import employees from XLSX file.
        Columns: First name, Last name, username
        Fake email and password will be generated.
        """
        file_name, _ = QFileDialog.getOpenFileName(self, self.tr('Open XLSX File'), '', self.tr('XLSX Files (*.xlsx)'))
        if file_name:
            try:
                persons = db_services.Person.create_persons_from_xlsx(file_name, self.project_id)
                self.persons = persons
                self.table_persons.persons = persons
                self.refresh_table()
            except Exception as e:
                QMessageBox.critical(self, self.tr('Error'), self.tr('Error: {}').format(e))

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

    def delete_person(self):
        row = self.table_persons.currentRow()
        if row == -1:
            QMessageBox.information(self, self.tr('Delete'),
                                  self.tr('Please select an entry first.\nClick on the corresponding row.'))
            return
        text_person = f'{self.table_persons.item(row, 0).text()} {self.table_persons.item(row, 1).text()}'
        res = QMessageBox.warning(self, self.tr('Delete'),
                                self.tr('Do you really want to permanently delete the data of...\n{}?').format(text_person),
                                QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            person_id = self.table_persons.item(row, 0).data(Qt.ItemDataRole.UserRole)
            try:
                self.controller.execute(person_commands.Delete(person_id))
                QMessageBox.information(self, self.tr('Delete'),
                                        self.tr('Deleted:\n{}').format(text_person))
            except Exception as e:
                QMessageBox.critical(self, self.tr('Error'), self.tr('Error: {}').format(e))
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
            self.setItem(row, 3, QTableWidgetItem(self.gender_visible_strings[p.gender.value]))
            self.setItem(row, 4, QTableWidgetItem(p.phone_nr))
            self.setItem(row, 5, QTableWidgetItem(p.address.street if p.address else ''))
            self.setItem(row, 6, QTableWidgetItem(p.address.postal_code if p.address else ''))
            self.setItem(row, 7, QTableWidgetItem(p.address.city if p.address else ''))

            # Team-Spalte: Text mit allen Teams + Edit-Button für Multi-Team-Support
            names = teams_by_person.get(p.id, [])
            team_names = ', '.join(names) if names else self.tr('No Team')

            widget_teams = QWidget()
            layout_teams = QHBoxLayout(widget_teams)
            layout_teams.setContentsMargins(2, 2, 2, 2)
            layout_teams.setSpacing(4)

            lb_teams = QLabel(team_names)
            lb_teams.setToolTip(team_names if names else '')
            bt_edit_teams = QPushButton('...')
            bt_edit_teams.setMaximumWidth(30)
            bt_edit_teams.setToolTip(self.tr('Edit team assignments'))
            bt_edit_teams.clicked.connect(partial(self.edit_team_assignments, p.id))

            layout_teams.addWidget(lb_teams, 1)
            layout_teams.addWidget(bt_edit_teams, 0)

            self.setCellWidget(row, 8, widget_teams)

        # Sortierung wieder aktivieren
        self.setSortingEnabled(True)

    def edit_team_assignments(self, person_id: UUID):
        """Öffnet den Dialog zur Verwaltung der Team-Zuordnungen einer Person."""
        person = db_services.Person.get(person_id)
        dlg = frm_team_assignments.DlgTeamAssignments(self, self.project_id, person)
        if dlg.exec():
            self.persons = db_services.Person.get_batch([p.id for p in self.persons])
            self.put_data_to_table()

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

        self.group_auth_data = QGroupBox(self.tr('Login Data'))
        self.group_auth_data_layout = QFormLayout(self.group_auth_data)
        self.layout.addWidget(self.group_auth_data)

        self.group_address_data = QGroupBox(self.tr('Address Data'))
        self.group_address_data_layout = QFormLayout(self.group_address_data)
        self.layout.addWidget(self.group_address_data)

        self.le_f_name = QLineEdit()
        self.le_l_name = QLineEdit()
        self.le_email = QLineEdit()
        self.cb_gender = QComboBox()
        self.cb_gender.addItems([n.name for n in Gender])
        self.le_phone_nr = QLineEdit()
        self.le_username = QLineEdit()
        self.le_password = QLineEdit()
        self.le_street = QLineEdit()
        self.le_postal_code = QLineEdit()
        self.le_city = QLineEdit()
        self.le_descriptive_name = QLineEdit()
        self.le_descriptive_name.setPlaceholderText(self.tr('Optional, e.g. "John Doe"'))

        self.group_person_data_layout.addRow(self.tr('First Name'), self.le_f_name)
        self.group_person_data_layout.addRow(self.tr('Last Name'), self.le_l_name)
        self.group_person_data_layout.addRow(self.tr('Email'), self.le_email)
        self.group_person_data_layout.addRow(self.tr('Gender'), self.cb_gender)
        self.group_person_data_layout.addRow(self.tr('Phone'), self.le_phone_nr)
        self.group_auth_data_layout.addRow(self.tr('Username'), self.le_username)
        self.group_auth_data_layout.addRow(self.tr('Password'), self.le_password)
        self.group_address_data_layout.addRow(self.tr('Street'), self.le_street)
        self.group_address_data_layout.addRow(self.tr('ZIP'), self.le_postal_code)
        self.group_address_data_layout.addRow(self.tr('City'), self.le_city)
        self.group_address_data_layout.addRow(self.tr('Descriptive Name'), self.le_descriptive_name)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)


class DlgPersonCreate(DlgPersonData):
    def __init__(self, parent: QWidget, project_id: UUID):
        self.created_person: schemas.PersonShow | None = None
        self.controller = command_base_classes.ContrExecUndoRedo()
        super().__init__(parent, project_id)

        self.layout.addWidget(self.button_box)

    def accept(self):
        street = self.le_street.text().strip()
        postal_code = self.le_postal_code.text().strip()
        city = self.le_city.text().strip()
        descriptive_name = self.le_descriptive_name.text().strip()
        person_address_is_set = street or postal_code or city or descriptive_name
        if person_address_is_set:
            address = schemas.AddressCreate(project_id=self.project_id, street=street, postal_code=postal_code, city=city, name=descriptive_name)
        else:
            address = None
        person = schemas.PersonCreate(f_name=self.le_f_name.text(), l_name=self.le_l_name.text(),
                                      email=self.le_email.text(), gender=Gender[self.cb_gender.currentText()],
                                      phone_nr=self.le_phone_nr.text(), username=self.le_username.text(),
                                      password=self.le_password.text(), address=address)

        create_command = person_commands.Create(person, self.project_id)
        self.controller.execute(create_command)
        self.created_person = create_command.created_person
        QMessageBox.information(self, self.tr('Person Created'),
                                self.tr('Person {} created in project {}').format(
                                    self.created_person.full_name,
                                    self.created_person.project.name))
        super().accept()

    @property
    def password(self):
        return self.le_password.text()


class DlgPersonModify(DlgPersonData):
    def __init__(self, parent: QWidget, project_id: UUID, person: schemas.PersonShow):
        self.project_id = project_id
        self.person = person
        self.controller = command_base_classes.ContrExecUndoRedo()

        super().__init__(parent, project_id)


    def _setup_ui(self):
        super()._setup_ui()
        self.group_auth_data.close()
        self.group_specific_data = QGroupBox(self.tr('Specific Data'))
        self.group_specific_data_layout = QFormLayout(self.group_specific_data)
        self.layout.addWidget(self.group_specific_data)

        self.le_id = QLineEdit()
        self.le_id.setReadOnly(True)
        self.spin_num_requested_assignments = QSpinBox()
        self.spin_num_requested_assignments.setMinimum(0)
        self.bt_team_assignments = QPushButton(self.tr('Edit...'), clicked=self.edit_team_assignments)
        self.bt_time_of_days = QPushButton(self.tr('Edit...'), clicked=self.edit_time_of_days)
        self.bt_comb_loc_possible = QPushButton(self.tr('Edit...'), clicked=self.edit_comb_loc_possible)
        self.bt_actor_loc_prefs = QPushButton(self.tr('Edit...'), clicked=self.edit_location_prefs)
        self.bt_actor_partner_loc_prefs = QPushButton(self.tr('Edit...'),
                                                      clicked=self.edit_partner_location_prefs)
        self.bt_skills = QPushButton(self.tr('Edit...'), clicked=self.select_skills)

        self.group_person_data_layout.addRow(self.tr('ID'), self.le_id)
        self.group_specific_data_layout.addRow(self.tr('Team Assignments'), self.bt_team_assignments)
        self.group_specific_data_layout.addRow(self.tr('Requested Assignments'), self.spin_num_requested_assignments)
        self.group_specific_data_layout.addRow(self.tr('Times of Day'), self.bt_time_of_days)
        self.group_specific_data_layout.addRow(self.tr('Location Combinations'), self.bt_comb_loc_possible)
        self.group_specific_data_layout.addRow(self.tr('Location Preferences'), self.bt_actor_loc_prefs)
        self.group_specific_data_layout.addRow(self.tr('Employee Preferences'), self.bt_actor_partner_loc_prefs)
        self.group_specific_data_layout.addRow(self.tr('Skills'), self.bt_skills)

        self.layout.addWidget(self.button_box)
        self.button_box.rejected.connect(self.reject)
        self.autofill()

    def accept(self):
        street = self.le_street.text().strip()
        postal_code = self.le_postal_code.text().strip()
        city = self.le_city.text().strip()
        descriptive_name = self.le_descriptive_name.text().strip()
        person_address_is_set = street or postal_code or city or descriptive_name
        self.person.f_name = self.le_f_name.text()
        self.person.l_name = self.le_l_name.text()
        self.person.email = self.le_email.text()
        self.person.gender = Gender[self.cb_gender.currentText()]
        self.person.phone_nr = self.le_phone_nr.text()
        self.person.requested_assignments = self.spin_num_requested_assignments.value()
        if person_address_is_set:
            if self.person.address is None:
                new_address = schemas.AddressCreate(project_id=self.project_id,
                                                    street=street,
                                                    postal_code=postal_code,
                                                    city=city,
                                                    name=descriptive_name)
                create_address_command = address_commands.Create(new_address)
                self.controller.execute(create_address_command)
                created_address = create_address_command.created_address
                self.person.address = created_address
            else:
                self.person.address.street = street
                self.person.address.postal_code = postal_code
                self.person.address.city = city
                self.person.address.name = descriptive_name
        else:
            self.person.address = None

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
        self.cb_gender.setCurrentText(self.person.gender.name)
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

    def edit_team_assignments(self):
        """Öffnet den Dialog zur Verwaltung der Team-Zuordnungen."""
        dlg = frm_team_assignments.DlgTeamAssignments(self, self.project_id, self.person)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.person = db_services.Person.get(self.person.id)

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
        self.controller = command_base_classes.ContrExecUndoRedo()

        self.locations = self.get_locations()

        self.table_locations = TableLocationsOfWork(self.locations)
        self.table_locations.cellDoubleClicked.connect(self.edit_location)
        self.layout.addWidget(self.table_locations)

        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

        self.bt_new = QPushButton(QIcon(os.path.join(self.path_to_icons, 'store--plus.png')), ' ' + self.tr('Create Facility'))
        self.bt_new.setFixedWidth(200)
        self.bt_new.clicked.connect(self.create_location)
        self.bt_edit = QPushButton(QIcon(os.path.join(self.path_to_icons, 'store--pencil.png')), ' ' + self.tr('Edit Facility'))
        self.bt_edit.setFixedWidth(200)
        self.bt_edit.clicked.connect(self.edit_location)
        self.bt_delete = QPushButton(QIcon(os.path.join(self.path_to_icons, 'store--minus.png')), ' ' + self.tr('Delete Facility'))
        self.bt_delete.setFixedWidth(200)
        self.bt_delete.clicked.connect(self.delete_location)

        self.layout_buttons.addWidget(self.bt_new)
        self.layout_buttons.addWidget(self.bt_edit)
        self.layout_buttons.addWidget(self.bt_delete)

    def get_locations(self) -> list[schemas.LocationOfWorkShow]:
        return db_services.LocationOfWork.get_all_from__project(self.project_id)

    def refresh_table(self):
        self.locations = self.get_locations()
        self.table_locations.locations = self.locations
        self.table_locations.clearContents()
        self.table_locations.setSortingEnabled(False)
        self.table_locations.put_data_to_table()
        self.table_locations.setSortingEnabled(True)

    def create_location(self):
        dlg = DlgLocationCreate(self, self.project_id)
        dlg.exec()
        self.refresh_table()

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

    def delete_location(self):
        row = self.table_locations.currentRow()
        if row == -1:
            QMessageBox.information(self, self.tr('Delete'),
                                  self.tr('You must first select an entry.\n'
                                        'Click on the corresponding row.'))
            return
        text_location = f'{self.table_locations.item(row, 0).text()} {self.table_locations.item(row, 1).text()}'
        res = QMessageBox.warning(self, self.tr('Delete'),
                                self.tr('Do you really want to permanently delete the data of...\n{}?').format(text_location),
                                QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            # UUID liegt als UserRole-Data auf Spalte 0 (analog Person-Delete),
            # NICHT als Text in der letzten Spalte — dort steht nr_actors.
            location_id = self.table_locations.item(row, 0).data(Qt.ItemDataRole.UserRole)
            self.controller.execute(location_of_work_commands.Delete(location_id))
            QMessageBox.information(self, self.tr('Delete'),
                                  self.tr('Deleted:\n{}').format(text_location))
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
        self.controller = command_base_classes.ContrExecUndoRedo()

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

        self.group_location_data_layout.addRow(self.tr('Name'), self.le_name)
        self.group_address_data_layout.addRow(self.tr('Street'), self.le_street)
        self.group_address_data_layout.addRow(self.tr('ZIP Code'), self.le_postal_code)
        self.group_address_data_layout.addRow(self.tr('City'), self.le_city)
        self.group_address_data_layout.addRow(self.tr('Descriptive Name'), self.le_descriptive_name)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.save_location)
        self.button_box.rejected.connect(self.reject)

    def save_location(self):
        street = self.le_street.text().strip()
        postal_code = self.le_postal_code.text().strip()
        city = self.le_city.text().strip()
        descriptive_name = self.le_descriptive_name.text().strip()
        address_is_set = street or postal_code or city or descriptive_name
        if address_is_set:
            address = schemas.AddressCreate(project_id=self.project_id, street=street, postal_code=postal_code, city=city, name=descriptive_name)
        else:
            address = None

        location = schemas.LocationOfWorkCreate(name=self.le_name.text(), address=address)

        cmd = location_of_work_commands.Create(location, self.project_id)
        try:
            self.controller.execute(cmd)
        except ApiError as exc:
            # 409 Conflict: typischerweise UNIQUE-Violation (Name bereits vergeben).
            # Andere ApiError: Server-/Validierungsproblem — als saubere Message anzeigen.
            if exc.status_code == 409:
                QMessageBox.warning(
                    self,
                    self.tr('Facility — Duplicate'),
                    self.tr('Ein Standort mit diesem Namen existiert bereits (ggf. zum Loeschen '
                            'vorgemerkt).\nBitte waehle einen anderen Namen.'),
                )
            else:
                QMessageBox.critical(
                    self,
                    self.tr('Facility Create Error'),
                    self.tr('Fehler: {}').format(exc.detail),
                )
            return
        QMessageBox.information(self, self.tr('Facility Created'), str(cmd.created_location))
        self.close()

    def reject(self):
        super().reject()


class DlgLocationCreate(DlgLocationData):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent, project_id=project_id)

        self.setWindowTitle(self.tr('Facility Data'))
        self.layout.addWidget(self.button_box)


class DlgLocationModify(DlgLocationData):
    def __init__(self, parent: QWidget, project_id: UUID, location_id: UUID):
        super().__init__(parent, project_id=project_id)

        self.setWindowTitle(self.tr('Facility Data'))
        self.location_id = location_id
        self.controller = command_base_classes.ContrExecUndoRedo()
        self.location_of_work = self.get_location_of_work()
        self.path_to_icons = os.path.join(os.path.dirname(__file__), 'resources', 'toolbar_icons', 'icons')

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
        self.layout_teams = QVBoxLayout()
        self.cb_teams = QComboBoxToFindData()
        self.cb_teams.currentIndexChanged.connect(self.change_team)
        self.lb_teams_info = QLabel()
        self.layout_teams.addWidget(self.cb_teams)
        self.layout_teams.addWidget(self.lb_teams_info)
        self.bt_time_of_days = QPushButton(self.tr('Edit...'), clicked=self.edit_time_of_days)
        self.bt_fixed_cast = QPushButton(self.tr('Edit...'), clicked=self.edit_fixed_cast)
        self.bt_skill_groups = QPushButton(self.tr('Edit...'), clicked=self.edit_skill_groups)

        self.group_location_data_layout.addRow(self.tr('ID'), self.le_id)
        self.layout_group_specific_data.addRow(self.tr('Staff Count'), self.spin_nr_actors)
        self.layout_group_specific_data.addRow(self.tr('Times of Day'), self.bt_time_of_days)
        self.layout_group_specific_data.addRow(self.tr('Team'), self.layout_teams)
        self.layout_group_specific_data.addRow(self.tr('Desired Staff'), self.bt_fixed_cast)
        self.layout_group_specific_data.addRow(self.tr('Skill Groups'), self.bt_skill_groups)
        self.layout.addWidget(self.button_box)

    def _autofill_widgets(self):
        self.le_name.setText(self.location_of_work.name)
        self.le_id.setText(str(self.location_of_work.id))
        if self.location_of_work.address:
            self.le_street.setText(self.location_of_work.address.street)
            self.le_postal_code.setText(self.location_of_work.address.postal_code)
            self.le_city.setText(self.location_of_work.address.city)
            self.le_descriptive_name.setText(self.location_of_work.address.name or '')
        self.spin_nr_actors.setValue(self.location_of_work.nr_actors)
        self.fill_teams()

    def save_location(self):
        street = self.le_street.text().strip()
        postal_code = self.le_postal_code.text().strip()
        city = self.le_city.text().strip()
        descriptive_name = self.le_descriptive_name.text().strip()

        address_is_set = street or postal_code or city or descriptive_name

        self.location_of_work.name = self.le_name.text().strip()
        if address_is_set:
            if self.location_of_work.address is None:
                address = schemas.AddressCreate(project_id=self.project_id, street=street, postal_code=postal_code, city=city, name=descriptive_name)
                create_address_command = address_commands.Create(address)
                self.controller.execute(create_address_command)
                created_address = create_address_command.created_address
                self.location_of_work.address = created_address
            else:
                self.location_of_work.address.street = street
                self.location_of_work.address.postal_code = postal_code
                self.location_of_work.address.city = city
                self.location_of_work.address.name = descriptive_name

        else:
            self.location_of_work.address = None
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

    def fill_teams(self):
        self.cb_teams.blockSignals(True)
        self.cb_teams.clear()
        teams: list[schemas.Team] = sorted(self.get_teams(), key=lambda t: t.name)
        self.cb_teams.addItem(QIcon(os.path.join(self.path_to_icons, 'users.png')), self.tr('No Team'), None)
        for team in teams:
            self.cb_teams.addItem(QIcon(os.path.join(self.path_to_icons, 'users.png')), team.name, team.id)
        self.set_curr_team()
        self.lb_teams_info.setText(self.get_team_info_text())
        self.cb_teams.blockSignals(False)

    def set_curr_team(self):
        curr_team = get_curr_team_of_location_at_date(location=self.location_of_work)
        curr_team_id = curr_team.id if curr_team else None
        self.cb_teams.setCurrentIndex(self.cb_teams.findData(curr_team_id))

    def get_team_info_text(self) -> str:
        if not (next_assignment__date := get_next_assignment_of_location(self.location_of_work, datetime.date.today())):
            return self.tr('No subsequent team assignment')
        next_assignment, date = next_assignment__date
        return self.tr('{team} from {date}').format(
            team=next_assignment.team.name if next_assignment else self.tr('No Team'),
            date=date_to_string(date))

    def edit_fixed_cast(self):
        dlg = DlgFixedCastBuilderLocationOfWork(self, self.location_of_work).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.location_of_work = db_services.LocationOfWork.get(self.location_of_work.id)

    def get_teams(self):
        return db_services.Team.get_all_from__project(self.project_id)

    def change_team(self):
        curr_team_assign = db_services.TeamLocationAssign.get_at__date(self.location_id, datetime.date.today())

        curr_team_id = curr_team_assign.team.id if curr_team_assign else None
        new_team_id = self.cb_teams.currentData()
        dlg = frm_assign_to_team.DlgAssignDate(self, curr_team_id, new_team_id)
        if dlg.exec():
            start_date = dlg.start_date_new_team
            if new_team_id:
                if not new_team_id and not curr_team_id:
                    return
                if (new_team_id == curr_team_id) and (start_date < curr_team_assign.end):
                    return
                command = location_of_work_commands.AssignToTeam(self.location_of_work.id, new_team_id, start_date)
                self.create_new_location_plan_periods(start_date, new_team_id, self.location_id)
            else:
                command = location_of_work_commands.LeaveTeam(self.location_of_work.id, start_date)
            self.controller.execute(command)
            self.location_of_work = self.get_location_of_work()
            self.fill_teams()
        else:
            self.cb_teams.blockSignals(True)
            self.cb_teams.setCurrentIndex(self.cb_teams.findData(curr_team_id))
            self.cb_teams.blockSignals(False)

    def edit_skill_groups(self):
        dlg = DlgSkillGroups(self, self.location_of_work)
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.location_of_work = self.get_location_of_work()
        else:
            dlg.controller.undo_all()

    def create_new_location_plan_periods(self, start_date: datetime.date, team_id: UUID, location_id: UUID):
        command = location_plan_period_commands.CreateLocationPlanPeriodsFromDate(start_date, location_id, team_id)
        self.controller.execute(command)
        for lpp in command.location_plan_periods:
            command = event_group_commands.Create(loc_act_plan_period_id=lpp.id)
            self.controller.execute(command)
