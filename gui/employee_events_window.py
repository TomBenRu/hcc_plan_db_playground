"""
Separates Hauptfenster für Employee Event Management.

Implementiert Employee Events als unabhängiges Window, das team-unabhängig 
funktioniert und parallel zu anderen hcc-plan Fenstern geöffnet bleiben kann.
"""

import logging
from typing import TYPE_CHECKING
from uuid import UUID

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QMenuBar

from .employee_event.frm_employee_event_main import FrmEmployeeEventMain

if TYPE_CHECKING:
    from .main_window import MainWindow

logger = logging.getLogger(__name__)


class EmployeeEventsWindow(QMainWindow):
    """
    Separates Fenster für Employee Event Management.
    
    Features:
    - Team-unabhängig (bleibt beim Team-Wechsel geöffnet)
    - Vollständige CRUD-Operationen für Employee Events
    - Kann parallel zu anderen hcc-plan Fenstern geöffnet bleiben
    - Echtes Schließen (nicht verstecken)
    """

    def __init__(self, parent: 'MainWindow', project_id: UUID):
        super().__init__(parent)

        self.parent_window = parent
        self.project_id = project_id

        self._setup_window()
        self._setup_ui()

        logger.info(f"Employee Events Window initialized for project {project_id}")

    def _setup_window(self):
        """Konfiguriert das Hauptfenster."""
        self.setWindowTitle(self.tr('Employee Events'))
        self.setMinimumSize(1000, 700)

        # Window-Flags für separates Fenster
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )

    def _setup_ui(self):
        """Erstellt das UI-Layout."""
        # Central Widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # Employee Event Main Widget
        self.main_widget = FrmEmployeeEventMain(self, self.project_id)
        layout.addWidget(self.main_widget)

        # Optional: Eigene Menüleiste für Employee Events
        self._setup_menu_bar()

    def _setup_menu_bar(self):
        """Erstellt eine optionale Menüleiste."""
        # Für jetzt keine eigene Menüleiste
        # Kann später erweitert werden falls gewünscht
        pass

    def closeEvent(self, event):
        """Behandelt das Schließen des Fensters."""
        # Echtes Schließen (wie gewünscht, nicht verstecken)

        # Window-Referenz in Parent löschen
        if self.parent_window:
            self.parent_window.employee_events_window = None

        logger.info("Employee Events Window closed")

        # Event akzeptieren (normales Schließen)
        event.accept()

        # Parent informieren falls nötig
        super().closeEvent(event)
