"""SMTP-Konfigurations-Dialog (Hinweis auf Web-Admin).

Vorher pflegte der Desktop-Client die SMTP-Zugangsdaten lokal in der
Systemkeychain. Seit Mai 2026 liegt die Konfiguration in der Server-DB
(verschlüsselt mit EMAIL_ENCRYPTION_KEY) und wird über die Web-Admin-
Oberfläche unter /admin/email-settings gepflegt.

Dieser Dialog ist nur noch ein Hinweis und ein Direkt-Link zur Web-UI.
"""

import logging

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from gui.api_client.client import get_api_client

logger = logging.getLogger(__name__)


class EmailConfigDialog(QDialog):
    """Hinweis-Dialog: Konfiguration läuft jetzt im Web-Admin."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("E-Mail-Konfiguration")
        self.setMinimumWidth(520)
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        info = QLabel(
            "<h3>SMTP-Konfiguration läuft jetzt im Web-Admin</h3>"
            "<p>Seit Mai 2026 werden SMTP-Server, Anmeldedaten und Absender-"
            "Identität zentral auf dem Server gepflegt. Der Desktop-Client "
            "hält keine SMTP-Credentials mehr.</p>"
            "<p>Öffne die Konfigurations-Seite mit einem Klick unten — "
            "dort kannst du auch eine Test-Mail an deinen Account schicken.</p>"
            "<p style='color:#666; font-size:11px;'>Voraussetzung: Du bist als "
            "Admin auf der Web-API angemeldet.</p>"
        )
        info.setWordWrap(True)
        info.setTextFormat(1)  # Qt.RichText
        layout.addWidget(info)

        button_layout = QHBoxLayout()
        open_button = QPushButton("Im Browser öffnen")
        close_button = QPushButton("Schließen")
        open_button.clicked.connect(self._open_admin_ui)
        close_button.clicked.connect(self.accept)
        button_layout.addStretch()
        button_layout.addWidget(open_button)
        button_layout.addWidget(close_button)
        layout.addLayout(button_layout)

    def _open_admin_ui(self):
        """Öffnet /admin/email-settings im Standard-Browser.

        Liest die Server-URL aus dem konfigurierten API-Client — damit
        landet der Admin auf der Instanz, gegen die der Desktop-Client
        gerade arbeitet (Dev-Server lokal vs. Render-Production).
        """
        try:
            base_url = get_api_client().base_url.rstrip("/")
            url = f"{base_url}/admin/email-settings"
            QDesktopServices.openUrl(QUrl(url))
            self.accept()
        except Exception:
            logger.exception("Konnte Admin-UI nicht öffnen")