"""Dialog box for creating a new project."""
from PySide6.QtWidgets import QDialog, QWidget, QVBoxLayout, QLabel, QLineEdit, QDialogButtonBox


class DlgCreateProject(QDialog):
    """Dialog box for creating a new project."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")

        self._setup_ui()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()

        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel("Enter the name of the new project:")
        self.le_project_name = QLineEdit()
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.layout_head.addWidget(self.lb_description)
        self.layout_body.addWidget(self.le_project_name)
        self.layout_foot.addWidget(self.button_box)

    @property
    def project_name(self) -> str:
        """Return the name of the new project."""
        return self.le_project_name.text()
