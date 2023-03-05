from uuid import UUID

from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout

from database import db_services


class SettingsProject(QDialog):
    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)
        self.setWindowTitle('Projekt-Einstellungen')

        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        self.project = db_services.get_project(project_id)
        print(self.project)
