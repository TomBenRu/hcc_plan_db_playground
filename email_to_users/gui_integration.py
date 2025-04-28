"""
GUI-Integration für die E-Mail-Funktionalität.

Dieses Modul bietet Klassen und Funktionen zur Integration der E-Mail-Funktionalität
in die Qt-basierte GUI des HCC Plan DB Playground-Projekts.
"""

import os
import logging
from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QCheckBox, QMessageBox, QFileDialog, QGroupBox,
    QFormLayout, QListWidget, QListWidgetItem, QProgressDialog
)
from PySide6.QtCore import Qt, QObject, Signal, Slot

from pony.orm import db_session, select

from database.models import Person, Team, PlanPeriod, Plan, Project

from .service import email_service
from .config import email_config, load_config_from_file

logger = logging.getLogger(__name__)


class EmailConfigDialog(QDialog):
    """Dialog zur Konfiguration der E-Mail-Einstellungen."""
    
    def __init__(self, parent=None):
        """Initialisiert den Dialog."""
        super().__init__(parent)
        self.setWindowTitle("E-Mail-Konfiguration")
        self.setMinimumWidth(500)
        
        self.setup_ui()
        self.load_config()
        
    def setup_ui(self):
        """Erstellt die UI-Elemente."""
        layout = QVBoxLayout(self)
        
        # SMTP-Server-Gruppe
        smtp_group = QGroupBox("SMTP-Server")
        smtp_layout = QFormLayout(smtp_group)
        
        self.host_edit = QLineEdit()
        self.port_edit = QLineEdit()
        self.username_edit = QLineEdit()
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        
        smtp_layout.addRow("SMTP-Server:", self.host_edit)
        smtp_layout.addRow("Port:", self.port_edit)
        smtp_layout.addRow("Benutzername:", self.username_edit)
        smtp_layout.addRow("Passwort:", self.password_edit)
        
        layout.addWidget(smtp_group)
        
        # Absender-Gruppe
        sender_group = QGroupBox("Absender")
        sender_layout = QFormLayout(sender_group)
        
        self.sender_email_edit = QLineEdit()
        self.sender_name_edit = QLineEdit()
        
        sender_layout.addRow("E-Mail-Adresse:", self.sender_email_edit)
        sender_layout.addRow("Name:", self.sender_name_edit)
        
        layout.addWidget(sender_group)
        
        # Verbindungs-Gruppe
        connection_group = QGroupBox("Verbindungsoptionen")
        connection_layout = QFormLayout(connection_group)
        
        self.use_tls_check = QCheckBox("TLS verwenden")
        self.use_ssl_check = QCheckBox("SSL verwenden")
        self.debug_mode_check = QCheckBox("Debug-Modus (keine E-Mails senden)")
        
        connection_layout.addRow(self.use_tls_check)
        connection_layout.addRow(self.use_ssl_check)
        connection_layout.addRow(self.debug_mode_check)
        
        layout.addWidget(connection_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.save_button = QPushButton("Speichern")
        self.cancel_button = QPushButton("Abbrechen")
        self.test_button = QPushButton("Verbindung testen")
        
        self.save_button.clicked.connect(self.save_config)
        self.cancel_button.clicked.connect(self.reject)
        self.test_button.clicked.connect(self.test_connection)
        
        button_layout.addWidget(self.test_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
    def load_config(self):
        """Lädt die Konfiguration in die UI-Elemente."""
        self.host_edit.setText(email_config.smtp_host)
        self.port_edit.setText(str(email_config.smtp_port))
        self.username_edit.setText(email_config.smtp_username)
        self.password_edit.setText(email_config.smtp_password)
        
        self.sender_email_edit.setText(email_config.default_sender_email)
        self.sender_name_edit.setText(email_config.default_sender_name)
        
        self.use_tls_check.setChecked(email_config.use_tls)
        self.use_ssl_check.setChecked(email_config.use_ssl)
        self.debug_mode_check.setChecked(email_config.debug_mode)
        
    def save_config(self):
        """Speichert die Konfiguration."""
        # Aktualisiere die Konfiguration
        email_config.smtp_host = self.host_edit.text()
        email_config.smtp_port = int(self.port_edit.text() or "587")
        email_config.smtp_username = self.username_edit.text()
        email_config.smtp_password = self.password_edit.text()
        
        email_config.default_sender_email = self.sender_email_edit.text()
        email_config.default_sender_name = self.sender_name_edit.text()
        
        email_config.use_tls = self.use_tls_check.isChecked()
        email_config.use_ssl = self.use_ssl_check.isChecked()
        email_config.debug_mode = self.debug_mode_check.isChecked()
        
        # Speichere in der Konfigurationsdatei
        config_dir = Path("configuration")
        if not config_dir.exists():
            config_dir.mkdir(exist_ok=True)
            
        config_path = config_dir / "email_config.toml"
        
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("[email]\n")
            f.write(f'smtp_host = "{email_config.smtp_host}"\n')
            f.write(f'smtp_port = {email_config.smtp_port}\n')
            f.write(f'smtp_username = "{email_config.smtp_username}"\n')
            f.write(f'smtp_password = "{email_config.smtp_password}"\n')
            f.write(f'default_sender_email = "{email_config.default_sender_email}"\n')
            f.write(f'default_sender_name = "{email_config.default_sender_name}"\n')
            f.write(f'use_tls = {str(email_config.use_tls).lower()}\n')
            f.write(f'use_ssl = {str(email_config.use_ssl).lower()}\n')
            f.write(f'debug_mode = {str(email_config.debug_mode).lower()}\n')
            
        QMessageBox.information(self, "Konfiguration gespeichert", 
                               "Die E-Mail-Konfiguration wurde erfolgreich gespeichert.")
        self.accept()
        
    def test_connection(self):
        """Testet die SMTP-Verbindung."""
        from email_to_users.sender import EmailSender
        import smtplib
        
        # Temporäre Konfiguration erstellen
        from email_to_users.config import EmailConfig
        temp_config = EmailConfig(
            smtp_host=self.host_edit.text(),
            smtp_port=int(self.port_edit.text() or "587"),
            smtp_username=self.username_edit.text(),
            smtp_password=self.password_edit.text(),
            use_tls=self.use_tls_check.isChecked(),
            use_ssl=self.use_ssl_check.isChecked(),
            debug_mode=False  # Debug-Modus für den Test deaktivieren
        )
        
        # Test-E-Mail-Sender erstellen
        sender = EmailSender(config=temp_config)
        
        try:
            # SMTP-Verbindung testen
            with sender._create_smtp_connection():
                QMessageBox.information(self, "Verbindungstest",
                                      "Die Verbindung zum SMTP-Server wurde erfolgreich hergestellt.")
        except smtplib.SMTPAuthenticationError:
            QMessageBox.critical(self, "Verbindungsfehler",
                               "Authentifizierungsfehler. Bitte überprüfen Sie Benutzername und Passwort.")
        except smtplib.SMTPConnectError:
            QMessageBox.critical(self, "Verbindungsfehler",
                               "Verbindung zum SMTP-Server fehlgeschlagen. Bitte überprüfen Sie Host und Port.")
        except Exception as e:
            QMessageBox.critical(self, "Verbindungsfehler",
                               f"Fehler beim Verbindungstest: {str(e)}")
