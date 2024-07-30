from uuid import UUID

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QComboBox, QVBoxLayout

from database import db_services, schemas


class DlgProjectSelect(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('Projekt auswählen')
        self.project_id: UUID | None = None

        self.layout = QVBoxLayout(self)

        self.combo_projects = QComboBox(self)
        self.layout.addWidget(self.combo_projects)

        self.fill_combo_projects()

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def fill_combo_projects(self):
        projects = db_services.Project.get_all()
        for p in projects:
            self.combo_projects.addItem(p.name, p.id)

    def accept(self):
        self.project_id = self.combo_projects.currentData()
        super().accept()
