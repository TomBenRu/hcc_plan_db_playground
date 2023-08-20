import datetime
import functools
from functools import partial
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QGridLayout, QMessageBox, QLabel, QLineEdit, QComboBox, \
    QGroupBox, QPushButton, QDialogButtonBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHBoxLayout, QSpinBox, \
    QMenu, QFormLayout, QHeaderView
from line_profiler_pycharm import profile

from database import db_services, schemas
from database.enums import Gender
from database.special_schema_requests import get_curr_team_of_location, get_curr_team_of_person_at_date, \
    get_curr_locations_of_team, get_locations_of_team_at_date, get_persons_of_team_at_date, \
    get_curr_team_of_location_at_date, get_next_assignment_of_location, get_next_assignment_of_person
from gui import frm_time_of_day, frm_comb_loc_possible, frm_actor_loc_prefs, frm_partner_location_prefs, \
    frm_assign_to_team
from .actions import Action
from .commands import time_of_day_commands, command_base_classes, person_commands, location_of_work_commands, \
    actor_loc_pref_commands, team_actor_assignment_commands
from .frm_fixed_cast import DlgFixedCast, DlgFixedCastBuilderLocationOfWork
from .tabbars import TabBar
from .tools.qcombobox_find_data import QComboBoxToFindData


class FrmMasterData(QWidget):
    def __init__(self, project_id: UUID):
        super().__init__()
        self.setWindowTitle('Stammdaten')
        self.setGeometry(50, 50, 1000, 600)

        self.project_id = project_id

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.tab_bar = TabBar(self, 'north', 12, 20, 200, False, 'tabbar_masterdata')
        self.layout.addWidget(self.tab_bar)

        self.widget_persons = WidgetPerson(project_id)

        self.widget_locations_of_work = WidgetLocationsOfWork(project_id)

        self.tab_bar.addTab(self.widget_persons, 'Mitarbeiter')
        self.tab_bar.addTab(self.widget_locations_of_work, 'Einrichtungen')
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

        self.layout.addWidget(self.table_persons)

        self.bt_new = QPushButton(QIcon('resources/toolbar_icons/icons/user--plus.png'), ' Person anlegen')
        self.bt_new.setFixedWidth(200)
        self.bt_new.clicked.connect(self.create_person)
        self.bt_edit = QPushButton(QIcon('resources/toolbar_icons/icons/user--pencil.png'), 'Person bearbeiten')
        self.bt_edit.setFixedWidth(200)
        self.bt_edit.clicked.connect(self.edit_person)
        self.bt_delete = QPushButton(QIcon('resources/toolbar_icons/icons/user--minus.png'), ' Person löschen')
        self.bt_delete.setFixedWidth(200)
        self.bt_delete.clicked.connect(self.delete_person)

        self.layout_buttons.addWidget(self.bt_new)
        self.layout_buttons.addWidget(self.bt_edit)
        self.layout_buttons.addWidget(self.bt_delete)

    def get_persons(self) -> list[schemas.PersonShow]:
        try:
            return [p for p in db_services.Person.get_all_from__project(self.project_id) if not p.prep_delete]
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')

    def refresh_table(self):
        self.persons = self.get_persons()
        self.table_persons.persons = self.persons
        self.table_persons.clearContents()
        self.table_persons.put_data_to_table()

    def create_person(self):
        dlg = FrmPersonCreate(self, self.project_id)
        dlg.exec()
        self.refresh_table()

    def edit_person(self):
        row = self.table_persons.currentRow()
        if row == -1:
            QMessageBox.information(self, 'Bearbeiten', 'Sie müssen zuerst einen Eintrag auswählen.\n'
                                                        'Klicken Sie dafür in die entsprechende Zeile.')
            return
        person = db_services.Person.get(UUID(self.table_persons.item(row, 9).text()))
        dlg = FrmPersonModify(self, self.project_id, person)
        if dlg.exec():
            self.refresh_table()

    def delete_person(self):
        row = self.table_persons.currentRow()
        if row == -1:
            QMessageBox.information(self, 'Löschen', 'Sie müssen zuerst einen Eintrag auswählen.\n'
                                                     'Klicken Sie dafür in die entsprechende Zeile.')
            return
        text_person = f'{self.table_persons.item(row, 0).text()} {self.table_persons.item(row, 1).text()}'
        res = QMessageBox.warning(self, 'Löschen',
                                  f'Wollen Sie die Daten von...\n{text_person}\n...wirklich entgültig löschen?',
                                  QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            person_id = UUID(self.table_persons.item(row, 9).text())
            try:
                deleted_person = db_services.Person.delete(person_id)
                QMessageBox.information(self, 'Löschen', f'Gelöscht:\n{deleted_person}')
            except Exception as e:
                QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')
        self.refresh_table()


class TablePersons(QTableWidget):
    def __init__(self, persons: list[schemas.PersonShow], project_id: UUID):
        super().__init__()

        self.persons = persons
        self.project_id = project_id

        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.horizontalHeader().setHighlightSections(False)
        self.cellDoubleClicked.connect(self.text_to_clipboard)
        self.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.headers = ['Vorname', 'Nachname', 'Email', 'Geschlecht', 'Telefon', 'Straße', 'PLZ', 'Ort', 'Team', 'id']
        self.setColumnCount(len(self.headers))
        self.setColumnWidth(6, 50)
        self.setHorizontalHeaderLabels(self.headers)
        self.hideColumn(9)
        self.gender_visible_strings = {'m': 'männlich', 'f': 'weiblich', 'd': 'divers'}

        self.put_data_to_table()
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def put_data_to_table(self):
        self.setRowCount(len(self.persons))
        for row, p in enumerate(self.persons):
            self.setItem(row, 0, QTableWidgetItem(p.f_name))
            self.setItem(row, 1, QTableWidgetItem(p.l_name))
            self.setItem(row, 2, QTableWidgetItem(p.email))
            self.setItem(row, 3, QTableWidgetItem(self.gender_visible_strings[p.gender.value]))
            self.setItem(row, 4, QTableWidgetItem(p.phone_nr))
            self.setItem(row, 5, QTableWidgetItem(p.address.street))
            self.setItem(row, 6, QTableWidgetItem(p.address.postal_code))
            self.setItem(row, 7, QTableWidgetItem(p.address.city))
            cb_team_of_actor = QComboBoxToFindData()
            cb_team_of_actor.addItem('', None)
            for team in sorted(db_services.Team.get_all_from__project(self.project_id), key=lambda t: t.name):
                cb_team_of_actor.addItem(team.name, team.id)
            curr_team = get_curr_team_of_person_at_date(person=p)
            cb_team_of_actor.setCurrentText(curr_team.name if curr_team else '')
            cb_team_of_actor.currentIndexChanged.connect(self.change_team)
            self.setCellWidget(row, 8, cb_team_of_actor)

            self.setItem(row, 9, QTableWidgetItem(str(p.id)))

    def text_to_clipboard(self, r, c):
        text = self.item(r, c).text()
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, 'Clipboard', f'{text}\nwurde kopiert.')

    def change_team(self, e):
        person_id = UUID(self.item(self.currentRow(), 9).text())
        sender: QComboBox = self.sender()
        team_id: UUID = sender.currentData()
        curr_team = get_curr_team_of_person_at_date(db_services.Person.get(person_id))
        dlg = frm_assign_to_team.DlgAssignDate(self, curr_team.id if curr_team else None, team_id)
        if not dlg.exec():
            sender.blockSignals(True)
            sender.setCurrentIndex(sender.findData(curr_team.id))
            sender.blockSignals(False)
            return
        person_full_name = f'{self.item(self.currentRow(), 0).text()} {self.item(self.currentRow(), 1).text()}'
        if team_id:
            person_commands.AssignToTeam(person_id, team_id, dlg.start_date_new_team).execute()
            next_assignment = get_next_assignment_of_person(db_services.Person.get(person_id), datetime.date.today())
            text_start = next_assignment.start.strftime("%d.%m.%Y") if next_assignment else 'ab sofort'
            text_team_name = db_services.Team.get(team_id).name
            QMessageBox.information(self, 'Person', f'Die Person "{person_full_name}" ist ab '
                                                    f'{text_start} dem Team '
                                                    f'"{text_team_name}" zugeordnet.')
        else:
            person_commands.LeaveTeam(person_id, dlg.start_date_new_team).execute()
            QMessageBox.information(self, 'Person', f'Die Person "{person_full_name}" ist ab '
                                                    f'{dlg.start_date_new_team.strftime("%d.%m.%Y")} '
                                                    f'keinem Team zugeordnet.')

        sender.blockSignals(True)
        curr_team = get_curr_team_of_person_at_date(person=db_services.Person.get(person_id))
        sender.setCurrentIndex(sender.findData(curr_team.id if curr_team else None))
        sender.blockSignals(False)


class FrmPersonData(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)

        self.setWindowTitle('Personendaten')

        self.project_id = project_id
        self.project = db_services.Project.get(project_id)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.group_person_data = QGroupBox('Personendaten')
        self.group_person_data_layout = QFormLayout(self.group_person_data)
        self.layout.addWidget(self.group_person_data)

        self.group_auth_data = QGroupBox('Anmeldedaten')
        self.group_auth_data_layout = QFormLayout(self.group_auth_data)
        self.layout.addWidget(self.group_auth_data)

        self.group_address_data = QGroupBox('Adressdaten')
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

        self.group_person_data_layout.addRow('Vorname', self.le_f_name)
        self.group_person_data_layout.addRow('Nachname', self.le_l_name)
        self.group_person_data_layout.addRow('Email', self.le_email)
        self.group_person_data_layout.addRow('Gerschlecht', self.cb_gender)
        self.group_person_data_layout.addRow('Telefon', self.le_phone_nr)
        self.group_auth_data_layout.addRow('Username', self.le_username)
        self.group_auth_data_layout.addRow('Passwort', self.le_password)
        self.group_address_data_layout.addRow('Straße', self.le_street)
        self.group_address_data_layout.addRow('Postleitzahl', self.le_postal_code)
        self.group_address_data_layout.addRow('Ort', self.le_city)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)


class FrmPersonCreate(FrmPersonData):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent, project_id)

        self.layout.addWidget(self.button_box)

    def accept(self):
        address = schemas.AddressCreate(street=self.le_street.text(), postal_code=self.le_postal_code.text(),
                                        city=self.le_city.text())
        person = schemas.PersonCreate(f_name=self.le_f_name.text(), l_name=self.le_l_name.text(),
                                      email=self.le_email.text(), gender=Gender[self.cb_gender.currentText()],
                                      phone_nr=self.le_phone_nr.text(), username=self.le_username.text(),
                                      password=self.le_password.text(), address=address)

        created = db_services.Person.create(person, self.project_id)
        QMessageBox.information(self, 'Person angelegt', f'{created}')
        super().accept()


class FrmPersonModify(FrmPersonData):
    @profile
    def __init__(self, parent: QWidget, project_id: UUID, person: schemas.PersonShow):
        super().__init__(parent, project_id)

        self.project_id = project_id
        self.person = person

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.sp_nr_requ_assignm = QSpinBox()
        self.sp_nr_requ_assignm.setMinimum(0)
        self.bt_time_of_days = QPushButton('bearbeiten', clicked=self.edit_time_of_days)
        self.bt_comb_loc_possible = QPushButton('Einrichtungskombinationen...', clicked=self.edit_comb_loc_possible)
        self.bt_actor_loc_prefs = QPushButton('Einrichtungspräferenzen', clicked=self.edit_location_prefs)
        self.bt_actor_partner_loc_prefs = QPushButton('Mitarbeiterpräferenzen',
                                                      clicked=self.edit_partner_location_prefs)

        self.group_auth_data.close()
        self.group_specific_data = QGroupBox('Spezielles')
        self.group_specific_data_layout = QFormLayout(self.group_specific_data)
        self.layout.addWidget(self.group_specific_data)

        self.group_specific_data_layout.addRow('Anz. gew. Einsätze', self.sp_nr_requ_assignm)
        self.group_specific_data_layout.addRow('Tageszeiten', self.bt_time_of_days)
        self.group_specific_data_layout.addRow('Einrichtungskombinationnen', self.bt_comb_loc_possible)
        self.group_specific_data_layout.addRow('Einrichtungspräferenzen', self.bt_actor_loc_prefs)
        self.group_specific_data_layout.addRow('Mitarbeiterpräferenzen', self.bt_actor_partner_loc_prefs)

        self.layout.addWidget(self.button_box)
        self.button_box.rejected.connect(self.reject)
        self.autofill()

    def accept(self):
        self.person.f_name = self.le_f_name.text()
        self.person.l_name = self.le_l_name.text()
        self.person.email = self.le_email.text()
        self.person.gender = Gender[self.cb_gender.currentText()]
        self.person.phone_nr = self.le_phone_nr.text()
        self.person.requested_assignments = self.sp_nr_requ_assignm.value()
        self.person.address.street = self.le_street.text()
        self.person.address.postal_code = self.le_postal_code.text()
        self.person.address.city = self.le_city.text()

        updated_person = db_services.Person.update(self.person)
        QMessageBox.information(self, 'Person Update',
                                f'Die Person wurde upgedatet:\n{updated_person.f_name} {updated_person.l_name}')
        super().accept()

    def reject(self):
        self.controller.undo_all()
        super().reject()

    def autofill(self):
        self.fill_person_data()
        self.fill_address_data()
        self.fill_requested_assignm()

    def fill_person_data(self):
        self.le_f_name.setText(self.person.f_name)
        self.le_l_name.setText(self.person.l_name)
        self.le_email.setText(self.person.email)
        self.cb_gender.setCurrentText(self.person.gender.name)
        self.le_phone_nr.setText(self.person.phone_nr)

    def fill_address_data(self):
        self.le_street.setText(self.person.address.street)
        self.le_postal_code.setText(self.person.address.postal_code)
        self.le_city.setText(self.person.address.city)

    def fill_requested_assignm(self):
        self.sp_nr_requ_assignm.setValue(self.person.requested_assignments)

    def edit_time_of_days(self):
        dlg = frm_time_of_day.DlgTimeOfDayEditListBuilderPerson(self, self.person).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.person = db_services.Person.get(self.person.id)

    def edit_comb_loc_possible(self):
        team_at_date_factory = parent_model_factory = partial(get_curr_team_of_person_at_date, self.person)

        dlg = frm_comb_loc_possible.DlgCombLocPossibleEditList(self, self.person, parent_model_factory, team_at_date_factory)
        if dlg.exec():
            self.person = db_services.Person.get(self.person.id)

    def edit_location_prefs(self):

        team_at_date_factory = functools.partial(get_curr_team_of_person_at_date, self.person)

        dlg = frm_actor_loc_prefs.DlgActorLocPref(self, self.person, None, team_at_date_factory)
        if not dlg.exec():
            return
        for loc_id, score in dlg.loc_id__results.items():
            if loc_id in dlg.loc_id__prefs:
                if dlg.loc_id__prefs[loc_id].score == score:
                    continue
                curr_loc_pref: schemas.ActorLocationPref = dlg.loc_id__prefs[loc_id]
                curr_loc_pref.score = score
                self.controller.execute(person_commands.RemoveActorLocationPref(self.person.id, curr_loc_pref.id))
                if score != 1:
                    new_pref = schemas.ActorLocationPrefCreate(**curr_loc_pref.model_dump())
                    create_command = actor_loc_pref_commands.Create(new_pref)
                    self.controller.execute(create_command)
                    created_pref_id = create_command.get_created_actor_loc_pref()

                    self.controller.execute(person_commands.PutInActorLocationPref(self.person.id, created_pref_id))
            else:
                if score == 1:
                    continue
                location = dlg.location_id__location[loc_id]
                new_loc_pref = schemas.ActorLocationPrefCreate(score=score, person=self.person,
                                                               location_of_work=location)
                create_command = actor_loc_pref_commands.Create(new_loc_pref)
                self.controller.execute(create_command)
                created_pref_id = create_command.get_created_actor_loc_pref()
                self.controller.execute(person_commands.PutInActorLocationPref(self.person.id, created_pref_id))

        self.controller.execute(actor_loc_pref_commands.DeleteUnused(self.person.project.id))
        self.person = db_services.Person.get(self.person.id)

    def edit_partner_location_prefs(self):
        team = get_curr_team_of_person_at_date(self.person)
        if not team:
            QMessageBox.critical(self, 'Mitarbeiterpräferenzen',
                                 f'{self.person.f_name} {self.person.l_name} '
                                 f'ist noch nicht Mitarbeiter*in eines Teams.')
            return

        team_at_date_factory = partial(get_curr_team_of_person_at_date, self.person)

        dlg = frm_partner_location_prefs.DlgPartnerLocationPrefs(self, self.person, self.person, None,
                                                                 team_at_date_factory)
        if not dlg.exec():
            return
        self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
        self.person = db_services.Person.get(self.person.id)


class WidgetLocationsOfWork(QWidget):
    def __init__(self, project_id: UUID):
        super().__init__()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.layout_buttons = QHBoxLayout()
        self.layout_buttons.setAlignment(Qt.AlignLeft)
        self.layout.addLayout(self.layout_buttons)

        self.project_id = project_id

        self.locations = self.get_locations()

        self.table_locations = TableLocationsOfWork(self.locations)
        self.layout.addWidget(self.table_locations)

        self.bt_new = QPushButton(QIcon('resources/toolbar_icons/icons/store--plus.png'), ' Einrichtung anlegen')
        self.bt_new.setFixedWidth(200)
        self.bt_new.clicked.connect(self.create_location)
        self.bt_edit = QPushButton(QIcon('resources/toolbar_icons/icons/store--pencil.png'), ' Einrichtung bearbeiten')
        self.bt_edit.setFixedWidth(200)
        self.bt_edit.clicked.connect(self.edit_location)
        self.bt_delete = QPushButton(QIcon('resources/toolbar_icons/icons/store--minus.png'), ' Einrichtung löschen')
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
        self.table_locations.put_data_to_table()

    def create_location(self):
        dlg = FrmLocationCreate(self, self.project_id)
        dlg.exec()
        self.refresh_table()

    def edit_location(self):
        row = self.table_locations.currentRow()
        if row == -1:
            QMessageBox.information(self, 'Löschen', 'Sie müssen zuerst einen Eintrag auswählen.\n'
                                                     'Klicken Sie dafür in die entsprechende Zeile.')
            return
        location_id = UUID(self.table_locations.item(row, self.table_locations.columnCount()-1).text())
        dlg = FrmLocationModify(self, self.project_id, location_id)
        if dlg.exec():
            self.refresh_table()

    def delete_location(self):
        row = self.table_locations.currentRow()
        if row == -1:
            QMessageBox.information(self, 'Löschen', 'Sie müssen zuerst einen Eintrag auswählen.\n'
                                                     'Klicken Sie dafür in die entsprechende Zeile.')
            return
        text_location = f'{self.table_locations.item(row, 0).text()} {self.table_locations.item(row, 1).text()}'
        res = QMessageBox.warning(self, 'Löschen',
                                  f'Wollen Sie die Daten von...\n{text_location}\n...wirklich entgültig löschen?',
                                  QMessageBox.StandardButton.Yes, QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            location_id = UUID(self.table_locations.item(row, self.table_locations.columnCount()-1).text())
            deleted_location = db_services.LocationOfWork.delete(location_id)
            QMessageBox.information(self, 'Löschen', f'Gelöscht:\n{deleted_location}')
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
        self.cellDoubleClicked.connect(self.text_to_clipboard)
        self.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.headers = ['Name', 'Straße', 'PLZ', 'Ort', 'Team', 'Besetung', 'id']
        self.setColumnCount(len(self.headers))
        self.setColumnWidth(4, 50)
        self.setHorizontalHeaderLabels(self.headers)

        self.put_data_to_table()
        self.hideColumn(self.columnCount()-1)
        self.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)

    def put_data_to_table(self):
        self.setRowCount(len(self.locations))
        for row, loc in enumerate(self.locations):
            self.setItem(row, 0, QTableWidgetItem(loc.name))
            self.setItem(row, 1, QTableWidgetItem(loc.address.street if loc.address else ''))
            self.setItem(row, 2, QTableWidgetItem(loc.address.postal_code if loc.address else ''))
            self.setItem(row, 3, QTableWidgetItem(loc.address.city if loc.address else ''))

            curr_team = get_curr_team_of_location_at_date(location=loc)
            txt_team = self.get_team_info_text(loc, curr_team)
            self.setItem(row, 4, QTableWidgetItem(txt_team))
            self.setItem(row, 5, QTableWidgetItem(str(loc.nr_actors)))
            self.setItem(row, 6, QTableWidgetItem(str(loc.id)))

    @staticmethod
    def get_team_info_text(location: schemas.LocationOfWorkShow, curr_team: schemas.Team | None) -> str:
        if curr_team:
            return curr_team.name
        if next_assignment__date := get_next_assignment_of_location(location, datetime.date.today()):
            next_assignment, date = next_assignment__date
            if next_assignment:
                return (f'{next_assignment.team.name if next_assignment else "Kein Team"} '
                        f'ab dem {date.strftime("%d.%m.%y")}')
        return ''


    def text_to_clipboard(self, r, c):
        text = self.item(r, c).text()
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, 'Clipboard', f'{text}\nwurde kopiert.')


class FrmLocationData(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)

        self.project_id = project_id
        self.project = db_services.Project.get(project_id)

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.group_location_data = QGroupBox('Einrichtungsdaten')
        self.group_location_data_layout = QFormLayout(self.group_location_data)
        self.layout.addWidget(self.group_location_data)
        self.group_address_data = QGroupBox('Adressdaten')
        self.group_address_data_layout = QFormLayout(self.group_address_data)
        self.layout.addWidget(self.group_address_data)

        self.le_name = QLineEdit()
        self.le_street = QLineEdit()
        self.le_postal_code = QLineEdit()
        self.le_city = QLineEdit()

        self.group_location_data_layout.addRow('Name', self.le_name)
        self.group_address_data_layout.addRow('Straße', self.le_street)
        self.group_address_data_layout.addRow('Postleitzahl', self.le_postal_code)
        self.group_address_data_layout.addRow('Ort', self.le_city)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.save_location)
        self.button_box.rejected.connect(self.reject)

    def save_location(self):
        address = schemas.AddressCreate(street=self.le_street.text(), postal_code=self.le_postal_code.text(),
                                        city=self.le_city.text())

        location = schemas.LocationOfWorkCreate(name=self.le_name.text(), address=address)

        created = db_services.LocationOfWork.create(location, self.project_id)
        QMessageBox.information(self, 'Einrichtung angelegt', f'{created}')
        self.close()

    def reject(self):
        super().reject()


class FrmLocationCreate(FrmLocationData):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent, project_id=project_id)

        self.setWindowTitle('Einrichtungsdaten')

        self.layout.addWidget(self.button_box)


class FrmLocationModify(FrmLocationData):
    def __init__(self, parent: QWidget, project_id: UUID, location_id: UUID):
        super().__init__(parent, project_id=project_id)

        self.setWindowTitle('Einrichtungsdaten')

        self.location_id = location_id

        self.controller = command_base_classes.ContrExecUndoRedo()

        self.location_of_work = self.get_location_of_work()

        self.group_specific_data = QGroupBox('Spezielles')
        self.layout_group_specific_data = QFormLayout(self.group_specific_data)
        self.layout.addWidget(self.group_specific_data)

        self.spin_nr_actors = QSpinBox()
        self.spin_nr_actors.setMinimum(1)
        self.layout_teams = QVBoxLayout()
        self.cb_teams = QComboBoxToFindData()
        self.cb_teams.currentIndexChanged.connect(self.change_team)
        self.lb_teams_info = QLabel()
        self.layout_teams.addWidget(self.cb_teams)
        self.layout_teams.addWidget(self.lb_teams_info)
        self.bt_time_of_days = QPushButton('bearbeiten', clicked=self.edit_time_of_days)
        self.bt_fixed_cast = QPushButton('bearbeiten', clicked=self.edit_fixed_cast)

        self.layout_group_specific_data.addRow('Besetzungsstärke', self.spin_nr_actors)
        self.layout_group_specific_data.addRow('Tageszeiten', self.bt_time_of_days)
        self.layout_group_specific_data.addRow('Team', self.layout_teams)
        self.layout_group_specific_data.addRow('Besetzung erwünscht', self.bt_fixed_cast)
        self.layout.addWidget(self.button_box)

        self.autofill()

    def save_location(self):
        self.location_of_work.name = self.le_name.text()
        self.location_of_work.address.street = self.le_street.text()
        self.location_of_work.address.postal_code = self.le_postal_code.text()
        self.location_of_work.address.city = self.le_city.text()
        self.location_of_work.nr_actors = self.spin_nr_actors.value()
        updated_location = db_services.LocationOfWork.update(self.location_of_work)
        QMessageBox.information(self, 'Location Update', f'Die Location wurde upgedatet:\n{updated_location.name}')
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
        teams: list[schemas.Team] = sorted([t for t in self.get_teams() if not t.prep_delete], key=lambda t: t.name)
        self.cb_teams.addItem(QIcon('resources/toolbar_icons/icons/users.png'), 'kein Team', None)
        for team in teams:
            self.cb_teams.addItem(QIcon('resources/toolbar_icons/icons/users.png'), team.name, team.id)
        self.set_curr_team()
        self.lb_teams_info.setText(self.get_team_info_text())
        self.cb_teams.blockSignals(False)

    def set_curr_team(self):
        curr_team = get_curr_team_of_location_at_date(location=self.location_of_work)
        curr_team_id = curr_team.id if curr_team else None
        self.cb_teams.setCurrentIndex(self.cb_teams.findData(curr_team_id))

    def get_team_info_text(self) -> str:
        if not (next_assignment__date := get_next_assignment_of_location(self.location_of_work, datetime.date.today())):
            return 'Keine nachfolgende Teamzuweisung'
        next_assignment, date = next_assignment__date
        return f'{next_assignment.team.name if next_assignment else "Kein Team"} ab dem {date.strftime("%d.%m.%y")}'

    def edit_fixed_cast(self):
        dlg = DlgFixedCastBuilderLocationOfWork(self, self.location_of_work).build()
        if dlg.exec():
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            self.location_of_work = db_services.LocationOfWork.get(self.location_of_work.id)

    def autofill(self):
        self.le_name.setText(self.location_of_work.name)
        self.le_street.setText(self.location_of_work.address.street)
        self.le_postal_code.setText(self.location_of_work.address.postal_code)
        self.le_city.setText(self.location_of_work.address.city)
        self.spin_nr_actors.setValue(self.location_of_work.nr_actors)
        self.fill_teams()
        # self.fill_time_of_days()

    def get_teams(self):
        return db_services.Team.get_all_from__project(self.project_id)

    def change_team(self):
        curr_team = get_curr_team_of_location_at_date(self.location_of_work)
        curr_team_id = curr_team.id if curr_team else None
        new_team_id = self.cb_teams.currentData()
        dlg = frm_assign_to_team.DlgAssignDate(self, curr_team_id, new_team_id)
        if dlg.exec():
            start_date = dlg.start_date_new_team
            if new_team_id:
                command = location_of_work_commands.AssignToTeam(self.location_of_work.id, new_team_id, start_date)
            else:
                command = location_of_work_commands.LeaveTeam(self.location_of_work.id, start_date)
            self.controller.execute(command)
            self.location_of_work = self.get_location_of_work()
            self.fill_teams()
        else:
            self.cb_teams.blockSignals(True)
            self.cb_teams.setCurrentIndex(self.cb_teams.findData(curr_team_id))
            self.cb_teams.blockSignals(False)
