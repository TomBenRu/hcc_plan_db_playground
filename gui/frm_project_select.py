from uuid import UUID

from PySide6.QtCore import QEvent, QObject
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QComboBox, QVBoxLayout, QCheckBox

from database import db_services, schemas
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.delayed_execution_timer import DelayedTimerSingleShot


class DlgProjectSelect(QDialog):
    def __init__(self, parent, project_id: UUID | None = None):
        super().__init__(parent)

        self.setWindowTitle('Projekt auswählen')
        self.project_id = project_id

        self.delayed_timer = DelayedTimerSingleShot(5000, self.accept)
        self.delayed_timer.start_timer()

        self._setup_ui()
        self.fill_combo_projects()
        self.install_recursive_event_filter(self)

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.combo_projects = QComboBoxToFindData(self)
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
        if self.project_id is not None:
            index = self.combo_projects.findData(self.project_id)
            if index >= 0:
                self.combo_projects.setCurrentIndex(index)
            else:
                self.project_id = None

    def install_recursive_event_filter(self, widget):
        # Install the event filter on the widget and all its children
        widget.installEventFilter(self)
        for child in widget.findChildren(QObject):
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        # Reset the timer if any interaction occurs
        if event.type() in (QEvent.KeyPress, QEvent.MouseMove, QEvent.MouseButtonPress):
            self.delayed_timer.start_timer()
        return super().eventFilter(obj, event)

    def accept(self):
        self.project_id = self.combo_projects.currentData()
        super().accept()
