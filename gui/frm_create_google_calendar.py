from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QFormLayout, QLabel, QComboBox, QLineEdit, QDialogButtonBox

from configuration.google_calenders import curr_calendars_handler
from database import db_services
from tools import custom_validators


class CreateGoogleCalendar(QDialog):
    def __init__(self, parent: QWidget, projekt_id: UUID):
        super().__init__(parent)
        self.setWindowTitle('Google-kalender erstellen')
        self.projekt_id = projekt_id

        self._setup_data()
        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QFormLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel('Hier können Sie einen Google-Kalender auf ihrem Google-Account anlegen.\n'
                                     'Wenn Sie in der Auswahlbox einen Mitarbeiter auswählen, kann dieser Kalender '
                                     'automatisch Zugriffsrechte über die eingegebene Email erhalten.')
        self.layout_head.addWidget(self.lb_description)

        self.combo_persons = QComboBox()
        self._fill_combo_persons()
        self.le_summary = QLineEdit()
        self.le_description = QLineEdit()
        self.combo_persons.currentIndexChanged.connect(self._combo_persons_index_changed)
        self.le_email = QLineEdit()
        self.le_email.setValidator(custom_validators.email_validator)
        self.layout_body.addRow('Mitarbeiter:', self.combo_persons)
        self.layout_body.addRow('Email:', self.le_email)
        self.layout_body.addRow('Kalendername:', self.le_summary)
        self.layout_body.addRow('Kurzbeschreibung:', self.le_description)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_data(self):
        self.project = db_services.Project.get(self.projekt_id)
        self.persons_of_project = db_services.Person.get_all_from__project(self.projekt_id)
        self.avail_google_calendars = curr_calendars_handler.get_calenders()
        print(self.avail_google_calendars)
        self.persons_for_new_calendar = sorted((p for p in self.persons_of_project
                                                if p.id not in {c.person_id
                                                                for c in self.avail_google_calendars.values()}),
                                               key=lambda x: x.full_name)

    def _fill_combo_persons(self):
        self.combo_persons.addItem('keine Person', None)
        for person in self.persons_for_new_calendar:
            self.combo_persons.addItem(person.full_name, person.id)

    def _combo_persons_index_changed(self):
        if self.combo_persons.currentData():
            self.le_description.setEnabled(True)
            self.le_summary.setText(f'{self.project.name} - Termine von {self.combo_persons.currentText()}')
            self.le_description.setText(f'{{"description": "Termine von {self.combo_persons.currentText()}", '
                                        f'"person_id": "{self.combo_persons.currentData()}"}}')
            self.le_description.setDisabled(True)
        else:
            self.le_description.setEnabled(True)
            self.le_summary.clear()
            self.le_description.clear()

    @property
    def new_calender_data(self) -> dict[str, str]:
        return {
            'summary': self.le_summary.text(),
            'description': self.le_description.text(),
            'location': 'Berlin',
            'timeZone': 'Europe/Berlin'
        }

    @property
    def email_for_access_control(self):
        return self.le_email.text()



