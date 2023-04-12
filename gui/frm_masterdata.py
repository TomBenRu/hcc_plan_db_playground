from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QWindow, QGuiApplication, QIcon, QMouseEvent
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QGridLayout, QMessageBox, QLabel, QLineEdit, QComboBox, \
    QGroupBox, QPushButton, QDialogButtonBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QHBoxLayout, QSpinBox, \
    QMenu, QListWidget, QFormLayout

from database import db_services, schemas
from database.enums import Gender
from gui import frm_time_of_day
from .actions import Action
from .commands import time_of_day_commands, command_base_classes, person_commands
from .frm_fixed_cast import FrmFixedCast
from .tabbars import TabBar


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
            persons = [p for p in db_services.Person.get_all_from__project(self.project_id) if not p.prep_delete]
            return persons
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
            for team in sorted(db_services.Team.get_all_from__project(self.project_id), key=lambda t: t.name):
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
        updated_person = db_services.Person.update_team_of_actor(person_id, team_id)
        if updated_person.team_of_actor:
            QMessageBox.information(self, 'Person', f'Die Person "{person_full_name}" wurde dem Team '
                                                    f'"{updated_person.team_of_actor.name}" zugeordnet.')
        else:
            QMessageBox.information(self, 'Person', f'Die Person "{person_full_name}" ist nun keinem Team zugeordnet.')


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
        self.button_box.accepted.connect(self.save_person)
        self.button_box.rejected.connect(self.reject)

    def save_person(self):
        ...


class FrmPersonCreate(FrmPersonData):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent, project_id)

        self.layout.addWidget(self.button_box)

    def save_person(self):
        address = schemas.AddressCreate(street=self.le_street.text(), postal_code=self.le_postal_code.text(),
                                        city=self.le_city.text())
        person = schemas.PersonCreate(f_name=self.le_f_name.text(), l_name=self.le_l_name.text(),
                                      email=self.le_email.text(), gender=Gender[self.cb_gender.currentText()],
                                      phone_nr=self.le_phone_nr.text(), username=self.le_username.text(),
                                      password=self.le_password.text(), address=address)
        try:
            created = db_services.Person.create(person, self.project_id)
            QMessageBox.information(self, 'Person angelegt', f'{created}')
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')


class FrmPersonModify(FrmPersonData):
    def __init__(self, parent: QWidget, project_id: UUID, person: schemas.PersonShow):
        super().__init__(parent, project_id)

        self.project_id = project_id
        self.person = person

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.reset_time_of_days_mode = False

        self.sp_nr_requ_assignm = QSpinBox()
        self.sp_nr_requ_assignm.setMinimum(0)
        self.cb_time_of_days = QComboBox()
        self.bt_time_of_days = QPushButton('bearbeiten')
        self.menu_bt_time_of_days = QMenu(self.bt_time_of_days)
        self.bt_time_of_days.setMenu(self.menu_bt_time_of_days)
        self.action_time_of_days_reset = Action(self, None, 'Reset von Projekt', None, self.reset_time_of_days)
        self.action_time_of_days_edit = Action(self, None, 'Ändern...', None, self.edit_time_of_days)
        self.menu_bt_time_of_days.addActions([self.action_time_of_days_edit, self.action_time_of_days_reset])
        self.widget_time_of_days_combi = QWidget()
        self.h_box_time_of_days_combi = QHBoxLayout(self.widget_time_of_days_combi)
        self.h_box_time_of_days_combi.setContentsMargins(0, 0, 0, 0)
        self.h_box_time_of_days_combi.addWidget(self.cb_time_of_days)
        self.h_box_time_of_days_combi.addWidget(self.bt_time_of_days)

        self.group_auth_data.close()
        self.group_specific_data = QGroupBox('Spezielles')
        self.group_specific_data_layout = QFormLayout(self.group_specific_data)
        self.layout.addWidget(self.group_specific_data)

        self.group_specific_data_layout.addRow('Anz. gew. Einsätze', self.sp_nr_requ_assignm)
        self.group_specific_data_layout.addRow('Tageszeiten', self.widget_time_of_days_combi)
        self.group_specific_data_layout.addRow('Einrichtungskombinationnen', QLabel('....wird noch'))
        self.group_specific_data_layout.addRow('Mitarbeiterpräferenzen', QLabel('....wird noch'))

        self.layout.addWidget(self.button_box)
        self.button_box.rejected.connect(self.cancel)
        self.autofill()

    def save_person(self):
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
        self.accept()

    def cancel(self):
        self.controller.undo_all()
        self.reject()

    def autofill(self):
        self.fill_person_data()
        self.fill_address_data()
        self.fill_time_of_days()
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

    def fill_time_of_days(self):
        self.cb_time_of_days.clear()
        time_of_days = sorted([t for t in self.person.time_of_days if not t.prep_delete], key=lambda x: x.start)
        for t in time_of_days:
            self.cb_time_of_days.addItem(QIcon('resources/toolbar_icons/icons/clock-select.png'),
                                         f'{t.name} -> {t.start.hour:02}:{t.start.minute:02} - '
                                         f'{t.end.hour:02}:{t.end.minute:02}', t)

    def edit_time_of_days(self):
        only_new_time_of_day, only_new_time_of_day_cause_parent_model, standard = frm_time_of_day.set_params_for__frm_time_of_day(self, self.person, 'project_defaults')
        dlg = frm_time_of_day.FrmTimeOfDay(self, self.cb_time_of_days.currentData(), self.project, only_new_time_of_day, standard)
        if not dlg.exec():
            return

        if dlg.chk_new_mode.isChecked():
            if only_new_time_of_day_cause_parent_model:
                '''Die aktuell gewählte Tageszeit ist dem parent-model zugeordnet 
                und wird daher aus time_of_days entfernt.'''
                self.person.time_of_days.remove(self.cb_time_of_days.currentData())
            if dlg.new_time_of_day.name in [t.name for t in self.person.time_of_days if not t.prep_delete]:
                '''Der Name der neu zu erstellenden Tageszeit ist schon in time_of_days vorhanden.'''
                QMessageBox.critical(dlg, 'Fehler', f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
                if only_new_time_of_day_cause_parent_model:  # Die zuvor entfernte Tagesz. wird wieder hinzugefügt
                    self.person.time_of_days.append(self.cb_time_of_days.currentData())
            else:
                if only_new_time_of_day_cause_parent_model:
                    '''Die aktuelle Tageszeit wurde aus times_of_days entfernt, weil sie zum Parent-Model gehöhrt.
                     Falls sie sich auch in den Personenstandarts befindet, wird sie auch da entfernt.'''
                    if self.cb_time_of_days.currentData().id in [t.id for t in self.person.time_of_day_standards]:
                        self.controller.execute(person_commands.RemoveTimeOfDayStandard(self.person.id, self.cb_time_of_days.currentData().id))

                create_command = time_of_day_commands.Create(dlg.new_time_of_day, self.project_id)
                self.controller.execute(create_command)
                created_t_o_d_id = create_command.time_of_day_id
                self.person.time_of_days.append(db_services.TimeOfDay.get(created_t_o_d_id))
                self.controller.execute(person_commands.Update(self.person))

                if dlg.chk_default.isChecked():
                    self.controller.execute(person_commands.NewTimeOfDayStandard(self.person.id, created_t_o_d_id))
                else:
                    self.controller.execute(person_commands.RemoveTimeOfDayStandard(self.person.id, created_t_o_d_id))
        elif dlg.to_delete_status:
            self.controller.execute(time_of_day_commands.Delete(dlg.curr_time_of_day.id))
            QMessageBox.information(self, 'Tageszeit Löschen',
                                    f'Die Tageszeit wird mit Bestätigen der vorhergehenden Dialogs gelöscht:\n'
                                    f'{dlg.curr_time_of_day}')
        else:
            if dlg.curr_time_of_day.name in [t.name for t in self.person.time_of_days
                                             if not t.prep_delete and dlg.curr_time_of_day.id != t.id]:
                QMessageBox.critical(dlg, 'Fehler',
                                     f'Die Tageszeit "{dlg.new_time_of_day.name}" ist schon vorhanden.')
            else:
                curr_t_o_d_id = dlg.curr_time_of_day.id
                self.controller.execute(time_of_day_commands.Update(dlg.curr_time_of_day))

                if dlg.chk_default.isChecked():
                    self.controller.execute(person_commands.NewTimeOfDayStandard(self.person.id, curr_t_o_d_id))
                else:
                    self.controller.execute(person_commands.RemoveTimeOfDayStandard(self.person.id, curr_t_o_d_id))

        self.person = db_services.Person.get(self.person.id)
        self.fill_time_of_days()
        return

    def reset_time_of_days(self):

        for t_o_d in self.person.time_of_days:
            '''Alle nicht nur zur Location gehörigen TimeOfDays werden nach self.time_of_days_to_delete geschoben.
            Diese werden dann mit Bestätigen des vorherigen Dialogs gelöscht.'''
            if not t_o_d.project_defaults:
                '''Das funktioniert, weil der Eintrag nicht wirklich gelöscht wird, 
                sondern nur das Attribut "prep_delete" gesetzt wird.'''
                self.controller.execute(time_of_day_commands.Delete(t_o_d.id))
        for t_o_d in self.person.time_of_day_standards:
            self.controller.execute(person_commands.RemoveTimeOfDayStandard(self.person.id, t_o_d.id))
        self.person.time_of_days.clear()  # notendig?
        for t_o_d in [t for t in self.project.time_of_days if not t.prep_delete]:
            self.person.time_of_days.append(t_o_d)
            if t_o_d.project_standard:
                self.controller.execute(person_commands.NewTimeOfDayStandard(self.person.id, t_o_d.id))

        self.controller.execute(person_commands.Update(self.person))
        self.person = db_services.Person.get(self.person.id)

        QMessageBox.information(self, 'Tageszeiten reset',
                                f'Die Tageszeiten wurden zurückgesetzt:\n'
                                f'{[(t_o_d.name, t_o_d.start, t_o_d.end) for t_o_d in self.person.time_of_days]}')
        self.fill_time_of_days()


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
            locations = db_services.LocationOfWork.get_all_from__project(self.project_id)
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
            try:
                deleted_location = db_services.LocationOfWork.delete(location_id)
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

    def put_data_to_table(self):
        self.setRowCount(len(self.locations))
        for row, loc in enumerate(self.locations):
            self.setItem(row, 0, QTableWidgetItem(loc.name))
            self.setItem(row, 1, QTableWidgetItem(loc.address.street if loc.address else ''))
            self.setItem(row, 2, QTableWidgetItem(loc.address.postal_code if loc.address else ''))
            self.setItem(row, 3, QTableWidgetItem(loc.address.city if loc.address else ''))
            self.setItem(row, 4, QTableWidgetItem(loc.team.name if loc.team else ''))
            self.setItem(row, 5, QTableWidgetItem(str(loc.nr_actors)))
            self.setItem(row, 6, QTableWidgetItem(str(loc.id)))

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
        self.button_box.rejected.connect(self.cancel)

    def save_location(self):
        address = schemas.AddressCreate(street=self.le_street.text(), postal_code=self.le_postal_code.text(),
                                        city=self.le_city.text())
        location = schemas.LocationOfWorkCreate(name=self.le_name.text(), address=address)
        try:
            created = db_services.LocationOfWork.create(location, self.project_id)
            QMessageBox.information(self, 'Einrichtung angelegt', f'{created}')
            self.close()
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')

    def cancel(self):
        self.reject()


class FrmLocationCreate(FrmLocationData):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent, project_id=project_id)

        self.setWindowTitle('Einrichtungsdaten')

        self.layout.addWidget(self.button_box)


class FrmLocationModify(FrmLocationData):
    def __init__(self, parent: QWidget, project_id: UUID, location_id: UUID):
        super().__init__(parent, project_id=project_id)

        self.new_time_of_day_to_delete: schemas.TimeOfDayShow | None = None
        self.time_of_days_to_update: list[schemas.TimeOfDayShow] = []
        self.time_of_days_to_delete: list[schemas.TimeOfDayShow] = []
        self.setWindowTitle('Einrichtungsdaten')

        self.location_id = location_id

        self.location_of_work = self.get_location_of_work()

        self.group_specific_data = QGroupBox('Spezielles')
        self.group_specific_data_layout = QGridLayout(self.group_specific_data)
        self.group_specific_data_layout.setColumnStretch(0, 1)
        self.group_specific_data_layout.setColumnStretch(1, 10)
        self.group_specific_data_layout.setColumnStretch(2, 1)
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
        for t_o_d in self.time_of_days_to_delete:
            db_services.TimeOfDay.delete(t_o_d.id)
        for t_o_d in self.time_of_days_to_update:
            db_services.TimeOfDay.update(t_o_d)
        updated_location = db_services.LocationOfWork.update(self.location_of_work)
        QMessageBox.information(self, 'Location Update', f'Die Location wurde upgedatet:\n{updated_location.name}')
        self.accept()

    def cancel(self):
        for t_o_d in self.new_time_of_day_to_delete:
            db_services.TimeOfDay.delete(t_o_d.id)
        self.reject()

    def get_location_of_work(self):
        location = db_services.LocationOfWork.get(self.location_id)
        return location

    def edit_time_of_days(self):
        frm_time_of_day.edit_time_of_days(self, self.location_of_work, self.project, 'project_defaults')

    def reset_time_of_days(self):
        default_time_of_days = db_services.Project.get(self.project_id).time_of_days
        frm_time_of_day.reset_time_of_days(self, self.location_of_work, default_time_of_days, 'project_defaults')

    def fill_time_of_days(self):
        self.cb_time_of_days.clear()
        time_of_days = sorted([t for t in self.location_of_work.time_of_days if not t.prep_delete], key=lambda t: t.start)
        for t in time_of_days:
            self.cb_time_of_days.addItem(QIcon('resources/toolbar_icons/icons/clock-select.png'),
                                         f'{t.name} -> {t.start.hour:02}:{t.start.minute:02} - '
                                         f'{t.end.hour:02}:{t.end.minute:02}', t)

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
        teams = db_services.Team.get_all_from__project(self.project_id)
        return teams
