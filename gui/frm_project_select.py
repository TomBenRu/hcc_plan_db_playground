from uuid import UUID

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QComboBox, QVBoxLayout, QCheckBox

from database import db_services, schemas


class DlgProjectSelect(QDialog):
    def __init__(self, parent):
        super().__init__(parent)

        self.setWindowTitle('Projekt auswählen')
        self.project_id: UUID | None = None

        self._setup_ui()
        self.fill_combo_projects()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.combo_projects = QComboBox(self)
        self.layout.addWidget(self.combo_projects)
        self.chk_save_for_next_time = QCheckBox('Projekt für nächstes Mal speichern')
        self.layout.addWidget(self.chk_save_for_next_time)
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
