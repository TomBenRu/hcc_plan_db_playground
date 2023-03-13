import sys
from abc import ABC, abstractmethod
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QWindow, QGuiApplication, QIcon, QMouseEvent
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QGridLayout, QMessageBox, QLabel, QLineEdit, QComboBox, \
    QGroupBox, QPushButton, QDialogButtonBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHBoxLayout, QSpinBox, \
    QMenu, QListWidget

from database import db_services, schemas
from database.enums import Gender
from gui.actions import Action
from gui.frm_fixed_cast import FrmFixedCast
from gui.frm_time_of_day import FrmTimeOfDay
from gui.tabbars import TabBar
from gui.tools.qcombobox_find_data import QComboBoxToFindData


class FrmMasterData(QWidget):
    def __init__(self, project_id: UUID):
        super().__init__()
        self.setWindowTitle('Stammdaten')
        self.setGeometry(50, 50, 800, 600)

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
        self.bt_delete = QPushButton(QIcon('resources/toolbar_icons/icons/user--minus.png'), ' Person löschen')
        self.bt_delete.setFixedWidth(200)
        self.bt_delete.clicked.connect(self.delete_person)

        self.layout_buttons.addWidget(self.bt_new)
        self.layout_buttons.addWidget(self.bt_delete)

    def get_persons(self) -> list[schemas.PersonShow]:
        try:
            persons = db_services.get_persons_of_project(self.project_id)
            return persons
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')

    def refresh_table(self):
        self.persons = self.get_persons()
        self.table_persons.persons = self.persons
        self.table_persons.clearContents()
        self.table_persons.put_data_to_table()

    def create_person(self):
        dlg = FrmPersonCreate(self.project_id)
        dlg.exec()
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
                deleted_person = db_services.delete_person(person_id)
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
        self.cellDoubleClicked.connect(self.text_to_clipboard)
        self.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.headers = ['Vorname', 'Nachname', 'Email', 'Geschlecht', 'Telefon', 'Straße', 'PLZ', 'Ort', 'Team', 'id']
        self.setColumnCount(len(self.headers))
        self.setColumnWidth(6, 50)
        self.setHorizontalHeaderLabels(self.headers)
        self.hideColumn(9)
        self.gender_visible_strings = {'m': 'männlich', 'f': 'weiblich', 'd': 'divers'}

        self.put_data_to_table()

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
            cb_team_of_actor = QComboBox()
            cb_team_of_actor.addItem('', None)
            for team in sorted(db_services.get_teams_of_project(self.project_id), key=lambda t: t.name):
                cb_team_of_actor.addItem(team.name, team)
            cb_team_of_actor.setCurrentText('' if not p.team_of_actor else p.team_of_actor.name)
            cb_team_of_actor.currentIndexChanged.connect(self.set_team)
            self.setCellWidget(row, 8, cb_team_of_actor)

            self.setItem(row, 9, QTableWidgetItem(str(p.id)))

    def text_to_clipboard(self, r, c):
        text = self.item(r, c).text()
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, 'Clipboard', f'{text}\nwurde kopiert.')

    def set_team(self, e):
        sender: QComboBox = self.sender()
        team: schemas.Team = sender.currentData()
        person_full_name = f'{self.item(self.currentRow(), 0).text()} {self.item(self.currentRow(), 1).text()}'
        person_id = UUID(self.item(self.currentRow(), 9).text())
        team_id = team.id if team else None
        updated_person = db_services.update_person__team_of_actor(person_id, team_id)
        if updated_person.team_of_actor:
            QMessageBox.information(self, 'Person', f'Die Person "{person_full_name}" wurde dem Team '
                                                    f'"{updated_person.team_of_actor.name}" zugeordnet.')
        else:
            QMessageBox.information(self, 'Person', f'Die Person "{person_full_name}" ist nun keinem Team zugeordnet.')



class FrmPersonCreate(QDialog):
    def __init__(self, project_id: UUID):
        super().__init__()

        self.setWindowTitle('Personendaten')

        self.project_id = project_id

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.group_person_data = QGroupBox('Personendaten')
        self.group_person_data_layout = QGridLayout()
        self.group_person_data.setLayout(self.group_person_data_layout)
        self.layout.addWidget(self.group_person_data)
        self.group_auth_data = QGroupBox('Anmeldedaten')
        self.group_auth_data_layout = QGridLayout()
        self.group_auth_data.setLayout(self.group_auth_data_layout)
        self.layout.addWidget(self.group_auth_data)
        self.group_address_data = QGroupBox('Adressdaten')
        self.group_address_data_layout = QGridLayout()
        self.group_address_data.setLayout(self.group_address_data_layout)
        self.layout.addWidget(self.group_address_data)

        self.lb_f_name = QLabel('Vorname')
        self.le_f_name = QLineEdit()
        self.lb_l_name = QLabel('Nachname')
        self.le_l_name = QLineEdit()
        self.lb_email = QLabel('Email')
        self.le_email = QLineEdit()
        self.lb_gender = QLabel('Geschlecht')
        self.cb_gender = QComboBox()
        self.cb_gender.addItems([n.name for n in Gender])
        self.lb_phone_nr = QLabel('Telefon')
        self.le_phone_nr = QLineEdit()
        self.lb_username = QLabel('Username')
        self.le_username = QLineEdit()
        self.lb_password = QLabel('Passwort')
        self.le_password = QLineEdit()
        self.lb_street = QLabel('Straße')
        self.le_street = QLineEdit()
        self.lb_postal_code = QLabel('Postleitzahl')
        self.le_postal_code = QLineEdit()
        self.lb_city = QLabel('Ort')
        self.le_city = QLineEdit()

        self.group_person_data_layout.addWidget(self.lb_f_name, 0, 0)
        self.group_person_data_layout.addWidget(self.le_f_name, 0, 1)
        self.group_person_data_layout.addWidget(self.lb_l_name, 1, 0)
        self.group_person_data_layout.addWidget(self.le_l_name, 1, 1)
        self.group_person_data_layout.addWidget(self.lb_email, 2, 0)
        self.group_person_data_layout.addWidget(self.le_email, 2, 1)
        self.group_person_data_layout.addWidget(self.lb_gender, 3, 0)
        self.group_person_data_layout.addWidget(self.cb_gender, 3, 1)
        self.group_person_data_layout.addWidget(self.lb_phone_nr, 4, 0)
        self.group_person_data_layout.addWidget(self.le_phone_nr, 4, 1)
        self.group_auth_data_layout.addWidget(self.lb_username, 0, 0)
        self.group_auth_data_layout.addWidget(self.le_username, 0, 1)
        self.group_auth_data_layout.addWidget(self.lb_password, 1, 0)
        self.group_auth_data_layout.addWidget(self.le_password, 1, 1)
        self.group_address_data_layout.addWidget(self.lb_street, 0, 0)
        self.group_address_data_layout.addWidget(self.le_street, 0, 1)
        self.group_address_data_layout.addWidget(self.lb_postal_code, 1, 0)
        self.group_address_data_layout.addWidget(self.le_postal_code, 1, 1)
        self.group_address_data_layout.addWidget(self.lb_city, 2, 0)
        self.group_address_data_layout.addWidget(self.le_city, 2, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.save_person)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def save_person(self):
        address = schemas.AddressCreate(street=self.le_street.text(), postal_code=self.le_postal_code.text(),
                                        city=self.le_city.text())
        person = schemas.PersonCreate(f_name=self.le_f_name.text(), l_name=self.le_l_name.text(),
                                      email=self.le_email.text(), gender=Gender[self.cb_gender.currentText()],
                                      phone_nr=self.le_phone_nr.text(), username=self.le_username.text(),
                                      password=self.le_password.text(), address=address)
        try:
            created = db_services.create_person(person, self.project_id)
            QMessageBox.information(self, 'Person angelegt', f'{created}')
            self.close()
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')


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
        try:
            locations = db_services.get_locations_of_work_of_project(self.project_id)
            return locations
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')

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
        dlg.exec()
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
            try:
                deleted_location = db_services.delete_location_of_work(location_id)
                QMessageBox.information(self, 'Löschen', f'Gelöscht:\n{deleted_location}')
            except Exception as e:
                QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')
        self.refresh_table()


class TableLocationsOfWork(QTableWidget):
    def __init__(self, locations: list[schemas.LocationOfWorkShow]):
        super().__init__()

        self.locations = locations

        self.setSortingEnabled(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.cellDoubleClicked.connect(self.text_to_clipboard)
        self.horizontalHeader().setStyleSheet("::section {background-color: teal; color:white}")

        self.headers = ['Name', 'Team', 'Besetung', 'Straße', 'PLZ', 'Ort', 'Team', 'id']
        self.setColumnCount(len(self.headers))
        self.setColumnWidth(4, 50)
        self.setHorizontalHeaderLabels(self.headers)

        self.put_data_to_table()
        self.hideColumn(self.columnCount()-1)
        print(self.columnCount())

    def put_data_to_table(self):
        self.setRowCount(len(self.locations))
        for row, loc in enumerate(self.locations):
            self.setItem(row, 0, QTableWidgetItem(loc.name))
            self.setItem(row, 1, QTableWidgetItem(loc.team.name if loc.team else ''))
            self.setItem(row, 2, QTableWidgetItem(str(loc.nr_actors)))
            self.setItem(row, 3, QTableWidgetItem(loc.address.street if loc.address else ''))
            self.setItem(row, 4, QTableWidgetItem(loc.address.postal_code if loc.address else ''))
            self.setItem(row, 5, QTableWidgetItem(loc.address.city if loc.address else ''))
            self.setItem(row, 6, QTableWidgetItem(loc.team.name if loc.team else ''))
            self.setItem(row, 7, QTableWidgetItem(str(loc.id)))

    def text_to_clipboard(self, r, c):
        text = self.item(r, c).text()
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, 'Clipboard', f'{text}\nwurde kopiert.')


class FrmLocationData(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent)

        self.project_id = project_id
        self.project = db_services.get_project(project_id)
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.group_location_data = QGroupBox('Einrichtungsdaten')
        self.group_location_data_layout = QGridLayout()
        self.group_location_data.setLayout(self.group_location_data_layout)
        self.layout.addWidget(self.group_location_data)
        self.group_address_data = QGroupBox('Adressdaten')
        self.group_address_data_layout = QGridLayout()
        self.group_address_data.setLayout(self.group_address_data_layout)
        self.layout.addWidget(self.group_address_data)

        self.lb_name = QLabel('Name')
        self.le_name = QLineEdit()
        self.lb_street = QLabel('Straße')
        self.le_street = QLineEdit()
        self.lb_postal_code = QLabel('Postleitzahl')
        self.le_postal_code = QLineEdit()
        self.lb_city = QLabel('Ort')
        self.le_city = QLineEdit()

        self.group_location_data_layout.addWidget(self.lb_name, 0, 0)
        self.group_location_data_layout.addWidget(self.le_name, 0, 1)
        self.group_address_data_layout.addWidget(self.lb_street, 0, 0)
        self.group_address_data_layout.addWidget(self.le_street, 0, 1)
        self.group_address_data_layout.addWidget(self.lb_postal_code, 1, 0)
        self.group_address_data_layout.addWidget(self.le_postal_code, 1, 1)
        self.group_address_data_layout.addWidget(self.lb_city, 2, 0)
        self.group_address_data_layout.addWidget(self.le_city, 2, 1)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.save_location)
        self.button_box.rejected.connect(self.reject)

    def save_location(self):
        address = schemas.AddressCreate(street=self.le_street.text(), postal_code=self.le_postal_code.text(),
                                        city=self.le_city.text())
        location = schemas.LocationOfWorkCreate(name=self.le_name.text(), address=address)
        try:
            created = db_services.create_location_of_work(location, self.project_id)
            QMessageBox.information(self, 'Einrichtung angelegt', f'{created}')
            self.close()
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')


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

        self.location_of_work = self.get_location_of_work()

        self.group_specific_data = QGroupBox('Spezielles')
        self.group_specific_data_layout = QGridLayout()
        self.group_specific_data_layout.setColumnStretch(0, 1)
        self.group_specific_data_layout.setColumnStretch(1, 10)
        self.group_specific_data_layout.setColumnStretch(2, 1)
        self.group_specific_data.setLayout(self.group_specific_data_layout)
        self.layout.addWidget(self.group_specific_data)

        self.lb_nr_actors = QLabel('Besetzungsstärke')
        self.spin_nr_actors = QSpinBox()
        self.spin_nr_actors.setMinimum(1)
        self.lb_teams = QLabel('Team')
        self.cb_teams = QComboBox()
        self.lb_time_of_days = QLabel('Tageszeiten')
        self.cb_time_of_days = QComboBox()
        self.bt_time_of_days = QPushButton('bearbeiten')
        self.menu_bt_time_of_days = QMenu(self.bt_time_of_days)
        self.bt_time_of_days.setMenu(self.menu_bt_time_of_days)
        self.action_time_of_days_reset = Action(self, None, 'Reset von Projekt', None, self.reset_time_of_days)
        self.action_time_of_days_edit = Action(self, None, 'Ändern...', None, self.edit_time_of_days)
        self.menu_bt_time_of_days.addActions([self.action_time_of_days_edit, self.action_time_of_days_reset])
        self.lb_fixed_cast = QLabel('Besetung erwünscht')
        self.bt_fixed_cast = QPushButton('bearbeiten', clicked=self.edit_fixed_cast)

        self.group_specific_data_layout.addWidget(self.lb_nr_actors, 0, 0)
        self.group_specific_data_layout.addWidget(self.spin_nr_actors, 0, 1)
        self.group_specific_data_layout.addWidget(self.lb_time_of_days, 1, 0)
        self.group_specific_data_layout.addWidget(self.cb_time_of_days, 1, 1)
        self.group_specific_data_layout.addWidget(self.bt_time_of_days, 1, 2)
        self.group_specific_data_layout.addWidget(self.lb_teams, 2, 0)
        self.group_specific_data_layout.addWidget(self.cb_teams, 2, 1)
        self.group_specific_data_layout.addWidget(self.lb_fixed_cast, 3, 0)
        self.group_specific_data_layout.addWidget(self.bt_fixed_cast, 3, 2)

        self.layout.addWidget(self.button_box)

        self.autofill()

    def save_location(self):
        self.location_of_work.name = self.le_name.text()
        self.location_of_work.address.street = self.le_street.text()
        self.location_of_work.address.postal_code = self.le_postal_code.text()
        self.location_of_work.address.city = self.le_city.text()
        self.location_of_work.nr_actors = self.spin_nr_actors.value()
        self.location_of_work.team = self.cb_teams.currentData()
        updated_location = db_services.update_location_of_work(self.location_of_work)
        QMessageBox.information(self, 'Location Update', f'Die Location wurde upgedatet:\n{updated_location.name}')
        self.close()

    def get_location_of_work(self):
        location = db_services.get_location_of_work_of_project(self.location_id)
        return location

    def edit_time_of_days(self):
        if not (curr_data := self.cb_time_of_days.currentData()):
            only_new_time_of_day_cause_project = True
        else:
            time_of_day_show_in_project = db_services.get_time_of_day(curr_data.id)

            '''Falls die Tageszeit dem Projekt zugewiesen ist, soll die abgeänderte Tageszeit als neue Tageszeit mit 
            Referenz zur Location gespeichert werden.'''
            only_new_time_of_day_cause_project = True if time_of_day_show_in_project.project_defaults else False

        dlg = FrmTimeOfDay(self, self.cb_time_of_days.currentData(), only_new_time_of_day=only_new_time_of_day_cause_project)
        if dlg.exec():  # Wenn der Dialog mit OK bestätigt wird...
            if dlg.to_delete_status:
                deleted_time_of_day = db_services.delete_time_of_day(dlg.curr_time_of_day.id)
                QMessageBox.information(self, 'Löschen', f'Die Tageszeit "{deleted_time_of_day.name}" wurde gelöscht.')
                return
            if dlg.chk_new_mode.isChecked():
                if only_new_time_of_day_cause_project:
                    self.location_of_work.time_of_days.remove(self.cb_time_of_days.currentData())
                if dlg.new_time_of_day.name in [t.name for t in self.location_of_work.time_of_days if not t.prep_delete]:
                    QMessageBox.critical(dlg, 'Fehler 483',
                                         f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
                    self.location_of_work = db_services.get_location_of_work_of_project(self.location_id)
                    self.cb_time_of_days.clear()
                    self.fill_time_of_days()
                else:
                    t_o_d_created = db_services.create_time_of_day(dlg.new_time_of_day, self.project_id)
                    self.location_of_work.time_of_days.append(t_o_d_created)
                    self.location_of_work = db_services.update_location_of_work(self.location_of_work)
                    QMessageBox.information(self, 'Tageszeit', f'Die Tageszeit wurde erstellt:\n{t_o_d_created}')
                    self.cb_time_of_days.clear()
                    self.fill_time_of_days()

            else:
                if dlg.curr_time_of_day.name in [t.name for t in self.location_of_work.time_of_days
                                                 if not t.prep_delete and dlg.curr_time_of_day.id != t.id]:
                    QMessageBox.critical(dlg, 'Fehler 494',
                                         f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
                else:
                    t_o_d_updated = db_services.update_time_of_day(dlg.curr_time_of_day)
                    QMessageBox.information(self, 'Tageszeit', f'Die Tageszeit wurde upgedated:\n{t_o_d_updated}')
                    self.location_of_work = db_services.get_location_of_work_of_project(self.location_id)
                    self.cb_time_of_days.clear()
                    self.fill_time_of_days()
                    return
                if dlg.to_delete_status:
                    time_of_day_deleted = db_services.delete_time_of_day(dlg.curr_time_of_day.id)
                    QMessageBox.information(self, 'Tageszeit Löschen', f'Die Tageszeit wurde gelöscht:\n'
                                                                       f'{time_of_day_deleted}')
                    self.location_of_work = db_services.get_location_of_work_of_project(self.location_id)
                    self.cb_time_of_days.clear()
                    self.fill_time_of_days()

    def reset_time_of_days(self):
        project = db_services.get_project(self.project_id)
        for t_o_d in self.location_of_work.time_of_days:
            if not t_o_d.project_defaults:
                db_services.delete_time_of_day(t_o_d.id)
        self.location_of_work.time_of_days.clear()
        for t_o_d in [t for t in project.time_of_days_default if not t.prep_delete]:
            self.location_of_work.time_of_days.append(t_o_d)
        self.location_of_work = db_services.update_location_of_work(self.location_of_work)
        QMessageBox.information(self, 'Tageszeiten reset', f'Die Tageszeiten wurden zurückgesetzt:\n'
                                                           f'{self.location_of_work}')
        self.cb_time_of_days.clear()
        self.fill_time_of_days()

    def fill_time_of_days(self):
        time_of_days = sorted([t for t in self.location_of_work.time_of_days if not t.prep_delete], key=lambda t: t.start)
        for t in time_of_days:
            self.cb_time_of_days.addItem(QIcon('resources/toolbar_icons/icons/clock-select.png'),
                                         f'{t.name} -> {t.start.hour:02}:{t.start.minute:02} - '
                                         f'{t.end.hour:02}:{t.end.minute:02}', t)

    def fill_dispatcher(self):
        self.cb_dispatcher.clear()
        persons = sorted([p for p in db_services.get_persons_of_project(self.project_id)
                          if not p.prep_delete], key=lambda t: t.f_name)
        for p in persons:
            self.cb_dispatcher.addItem(QIcon('resources/toolbar_icons/icons/user-female.png'),
                                       f'{p.f_name} {p.l_name}', p)
        self.cb_dispatcher.setCurrentIndex(self.cb_dispatcher.findData(self.location_of_work.dispatcher))

    def edit_fixed_cast(self):
        if not self.location_of_work.team:
            QMessageBox.critical(self, 'Besetzung', 'Sie mussen diese Einrichtung zuerst einem Team zuteilen,'
                                                    'um eine Besetzungsstrategie zu definieren.')
            return
        dlg = FrmFixedCast(self, self.location_of_work)
        dlg.exec()

    def autofill(self):
        self.le_name.setText(self.location_of_work.name)
        self.le_street.setText(self.location_of_work.address.street)
        self.le_postal_code.setText(self.location_of_work.address.postal_code)
        self.le_city.setText(self.location_of_work.address.city)
        self.spin_nr_actors.setValue(self.location_of_work.nr_actors)
        teams: list[schemas.Team] = sorted([t for t in self.get_teams() if not t.prep_delete], key=lambda t: t.name)
        self.cb_teams.addItem(QIcon('resources/toolbar_icons/icons/users.png'), 'kein Team', None)
        for team in teams:
            self.cb_teams.addItem(QIcon('resources/toolbar_icons/icons/users.png'), team.name, team)
        team = self.location_of_work.team
        self.cb_teams.setCurrentText(team.name) if team else self.cb_teams.setCurrentText('kein Team')
        self.fill_time_of_days()

    def get_teams(self):
        teams = db_services.get_teams_of_project(self.project_id)
        return teams



