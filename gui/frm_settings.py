from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QGridLayout, QLabel, QLineEdit, QComboBox

from database import db_services


class SettingsProject(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)
        self.setWindowTitle('Projekt-Einstellungen')

        self.layout = QGridLayout()
        self.setLayout(self.layout)

        self.project = db_services.get_project(project_id)

        self.lb_name = QLabel('Name')
        self.le_name = QLineEdit()
        self.lb_time_of_days = QLabel('Tageszeiten')
        self.cb_time_of_days = QComboBox()

        self.layout.addWidget(self.lb_name, 0, 0)
        self.layout.addWidget(self.le_name, 0, 1)
        self.layout.addWidget(self.lb_time_of_days, 1, 0)
        self.layout.addWidget(self.cb_time_of_days, 1, 1)

        self.autofill()

    def autofill(self):
        self.le_name.setText(self.project.name)
        self.cb_time_of_days.addItems([t.name for t in self.project.time_of_days])
