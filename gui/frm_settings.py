import datetime
from uuid import UUID

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox, QHBoxLayout,
                               QGroupBox, QPushButton, QTimeEdit, QMessageBox)

from database import db_services, schemas


class SettingsProject(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)
        self.setWindowTitle('Projekt-Einstellungen')

        self.project = db_services.get_project(project_id)

        self.layout = QHBoxLayout()
        self.setLayout(self.layout)

        self.group_project_data = QGroupBox('Projektdaten')
        self.group_time_of_day_data = QGroupBox('Tageszeit')
        self.layout_group_project_data = QGridLayout()
        self.layout_group_time_of_day_data = QGridLayout()
        self.group_project_data.setLayout(self.layout_group_project_data)
        self.group_time_of_day_data.setLayout(self.layout_group_time_of_day_data)
        self.layout.addWidget(self.group_project_data)
        self.layout.addWidget(self.group_time_of_day_data)

        self.lb_name = QLabel('Name')
        self.le_name = QLineEdit()
        self.bt_name_save = QPushButton('Projektname ändern')
        self.lb_time_of_days = QLabel('Tageszeiten')
        self.cb_time_of_days = QComboBox()
        self.cb_time_of_days.currentIndexChanged.connect(self.set_time_of_day_values)
        self.bt_tod_delete = QPushButton('Tageszeit löschen')

        self.lb_tod_name = QLabel('Name')
        self.le_tod_name = QLineEdit()
        self.lb_tod_start = QLabel('Zeitpunkt Start')
        self.te_tod_start = QTimeEdit()
        self.lb_tod_end = QLabel('Zeitpunkt Ende')
        self.te_tod_end = QTimeEdit()
        self.bt_tod_save = QPushButton('Tageszeit speichern')
        self.bt_tod_save.clicked.connect(self.save_time_of_day)

        self.layout_group_project_data.addWidget(self.lb_name, 0, 0)
        self.layout_group_project_data.addWidget(self.le_name, 0, 1)
        self.layout_group_project_data.addWidget(self.bt_name_save, 1, 1)
        self.layout_group_project_data.addWidget(self.lb_time_of_days, 2, 0)
        self.layout_group_project_data.addWidget(self.cb_time_of_days, 2, 1)
        self.layout_group_project_data.addWidget(self.bt_tod_delete, 3, 1)

        self.layout_group_time_of_day_data.addWidget(self.lb_tod_name, 0, 0)
        self.layout_group_time_of_day_data.addWidget(self.le_tod_name, 0, 1)
        self.layout_group_time_of_day_data.addWidget(self.lb_tod_start, 1, 0)
        self.layout_group_time_of_day_data.addWidget(self.te_tod_start, 1, 1)
        self.layout_group_time_of_day_data.addWidget(self.lb_tod_end, 2, 0)
        self.layout_group_time_of_day_data.addWidget(self.te_tod_end, 2, 1)
        self.layout_group_time_of_day_data.addWidget(self.bt_tod_save, 3, 1)

        self.autofill()

    def autofill(self):
        self.le_name.setText(self.project.name)
        self.cb_time_of_days.clear()
        self.cb_time_of_days.addItems([t.name for t in self.project.time_of_days if not t.prep_delete])

    def set_time_of_day_values(self):
        tod_name = self.cb_time_of_days.currentText()
        for tod in self.project.time_of_days:
            if tod.name == tod_name and not tod.prep_delete:
                self.le_tod_name.setText(tod.name)
                self.te_tod_start.setTime(tod.start)
                self.te_tod_end.setTime(tod.end)
                break

    def save_time_of_day(self):
        name = self.le_tod_name.text()
        if not name:
            QMessageBox.information(self, 'Fehler', 'Sie müsser einen Namen für diese Tageszeit angeben.')
            return
        start = datetime.time(self.te_tod_start.time().hour(), self.te_tod_start.time().minute())
        end = datetime.time(self.te_tod_end.time().hour(), self.te_tod_end.time().minute())

        if tods := [tod for tod in self.project.time_of_days if tod.name == name and not tod.prep_delete]:
            db_services.delete_time_of_day(tods[0].id)
            self.project.time_of_days.remove(tods[0])
        new_time_of_day = schemas.TimeOfDayCreate(name=name, start=start, end=end)
        created_time_of_day = db_services.create_time_of_day(new_time_of_day, self.project.id)
        self.project.time_of_days.append(created_time_of_day)
        self.project.name = self.le_name.text()
        project_updated = db_services.update_project(self.project)
        self.project = project_updated
        QMessageBox.information(self, 'Tageszeit', f'Die Tageszeit {created_time_of_day.name} wurde upgedatet bzw. dem '
                                                   f'Projekt {self.project.name} hinzugefügt.')
        self.autofill()
        self.cb_time_of_days.setCurrentText(created_time_of_day.name)


