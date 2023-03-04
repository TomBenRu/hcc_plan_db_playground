from uuid import UUID

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QGridLayout, QMessageBox, QLabel, QLineEdit, QComboBox, \
    QGroupBox, QPushButton, QDialogButtonBox

from database import db_services, schemas
from database.enums import Gender
from gui.tabbars import TabBar


class FrmMasterData(QDialog):
    def __init__(self, project_id: UUID):
        super().__init__()
        self.setWindowTitle('Stammdaten')
        self.setGeometry(50, 50, 800, 600)

        self.project_id = project_id

        self.persons = self.get_persons()
        self.locations_of_work = self.get_locations()

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.tab_bar = TabBar(self, 'north', 12, 20, 200, False, 'tabbar_masterdata')
        self.layout.addWidget(self.tab_bar)

        self.widget_persons = QWidget()
        self.widget_locations_of_work = QWidget()

        self.tab_bar.addTab(self.widget_persons, 'Mitarbeiter')
        self.tab_bar.addTab(self.widget_locations_of_work, 'Einrichtungen')

        self.layout.addWidget(self.tab_bar)

        self.widget_persons_layout = QVBoxLayout()
        self.widget_persons.setLayout(self.widget_persons_layout)
        self.bt_new_person = QPushButton('Person anlegen...')
        self.bt_new_person.clicked.connect(self.create_person)
        self.widget_persons_layout.addWidget(self.bt_new_person)

    def get_persons(self):
        try:
            persons = db_services.get_persons_of_project(self.project_id)
            print(f'{persons=}')
            return persons
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')

    def get_locations(self):
        try:
            locations = db_services.get_locations_of_work_of_project(self.project_id)
            return locations
        except Exception as e:
            QMessageBox.critical(self, 'Fehler', f'Fehler: {e}')

    def create_person(self):
        dlg = FrmPersonCreate(self.project_id)
        dlg.exec()


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


