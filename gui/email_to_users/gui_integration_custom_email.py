"""
Teil 4 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für benutzerdefinierte E-Mails.
"""
from uuid import UUID

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QCheckBox, QGroupBox, QFormLayout, 
    QListWidget, QListWidgetItem, QProgressDialog, QMessageBox
)
from PySide6.QtCore import Qt

from database import db_services
from email_to_users.service import email_service


class CustomEmailDialog(QDialog):
    """Dialog zum Senden von benutzerdefinierten E-Mails."""
    
    def __init__(self, parent=None, project_id: UUID = None):
        """Initialisiert den Dialog."""
        super().__init__(parent)
        self.setWindowTitle("Benutzerdefinierte E-Mail senden")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)
        
        self.project_id = project_id

        self.setup_ui()
        self.load_recipients()
        
    def setup_ui(self):
        """Erstellt die UI-Elemente."""
        layout = QVBoxLayout(self)
        
        # E-Mail-Kopf
        header_group = QGroupBox("E-Mail-Kopf")
        header_layout = QFormLayout(header_group)
        
        self.subject_edit = QLineEdit()
        header_layout.addRow("Betreff:", self.subject_edit)
        
        layout.addWidget(header_group)
        
        # Empfänger-Gruppe
        recipients_group = QGroupBox("Empfänger")
        recipients_layout = QVBoxLayout(recipients_group)
        
        # Empfängertyp-Auswahl
        recipient_type_layout = QHBoxLayout()
        
        self.person_select_radio = QCheckBox("Einzelne Personen")
        self.team_select_radio = QCheckBox("Team")
        self.project_select_radio = QCheckBox("Projekt")
        
        self.person_select_radio.setChecked(True)
        
        recipient_type_layout.addWidget(self.person_select_radio)
        recipient_type_layout.addWidget(self.team_select_radio)
        recipient_type_layout.addWidget(self.project_select_radio)
        
        # Team- und Projekt-Auswahl
        selection_layout = QHBoxLayout()
        
        self.team_combo = QComboBox()
        self.project_combo = QComboBox()
        
        self.team_combo.setEnabled(False)
        self.project_combo.setEnabled(False)
        
        selection_layout.addWidget(QLabel("Team:"))
        selection_layout.addWidget(self.team_combo)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(QLabel("Projekt:"))
        selection_layout.addWidget(self.project_combo)
        
        # Personenliste
        self.person_list = QListWidget()
        self.person_list.setSelectionMode(QListWidget.MultiSelection)
        
        # Verbinde Checkboxen mit Aktionen
        self.person_select_radio.toggled.connect(self.toggle_person_list)
        self.team_select_radio.toggled.connect(self.toggle_team_combo)
        self.project_select_radio.toggled.connect(self.toggle_project_combo)
        
        recipients_layout.addLayout(recipient_type_layout)
        recipients_layout.addLayout(selection_layout)
        recipients_layout.addWidget(self.person_list)
        
        layout.addWidget(recipients_group)
        
        # E-Mail-Inhalt
        content_group = QGroupBox("E-Mail-Inhalt")
        content_layout = QVBoxLayout(content_group)
        
        self.plain_radio = QCheckBox("Nur Plaintext")
        self.html_radio = QCheckBox("HTML-E-Mail")
        
        self.plain_radio.setChecked(True)
        
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(self.plain_radio)
        radio_layout.addWidget(self.html_radio)
        radio_layout.addStretch()
        
        self.plain_radio.toggled.connect(self.toggle_content_type)
        self.html_radio.toggled.connect(self.toggle_content_type)
        
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("E-Mail-Inhalt hier eingeben... (Personalisierung möglich mit {name}, {email})")
        
        content_layout.addLayout(radio_layout)
        content_layout.addWidget(self.content_edit)
        
        layout.addWidget(content_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.send_button = QPushButton("Senden")
        self.cancel_button = QPushButton("Abbrechen")
        
        self.send_button.clicked.connect(self.send_email)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)

    def load_recipients(self):
        """Lädt Empfänger, Teams und Projekte."""
        # Lade Personen
        persons = sorted(db_services.Person.get_all_from__project(self.project_id), key=lambda x: x.full_name)
        for person in persons:
            item = QListWidgetItem(f"{person.full_name} ({person.email})")
            item.setData(Qt.ItemDataRole.UserRole, person.id)
            self.person_list.addItem(item)
        
        # Lade Teams
        teams = sorted(db_services.Team.get_all_from__project(self.project_id), key=lambda x: x.name)
        for team in teams:
            self.team_combo.addItem(team.name, team.id)
        
        # Lade Projekte
        project = db_services.Project.get(self.project_id)
        self.project_combo.addItem(project.name, project.id)
        self.project_combo.setEnabled(False)
    
    def toggle_person_list(self, checked):
        """Aktiviert/deaktiviert die Personenliste."""
        self.person_list.setEnabled(checked)
        
    def toggle_team_combo(self, checked):
        """Aktiviert/deaktiviert die Team-Auswahl."""
        self.team_combo.setEnabled(checked)
        
    def toggle_project_combo(self, checked):
        """Aktiviert/deaktiviert die Projekt-Auswahl."""
        self.project_combo.setEnabled(checked)
        
    def toggle_content_type(self, checked):
        """Wechselt zwischen Plaintext und HTML."""
        if self.plain_radio.isChecked() and self.html_radio.isChecked():
            # Stelle sicher, dass immer mindestens eine Option ausgewählt ist
            if self.sender() == self.plain_radio:
                self.html_radio.setChecked(False)
            else:
                self.plain_radio.setChecked(False)
    
    def send_email(self):
        """Sendet die E-Mail."""
        # Validierung
        if not self.subject_edit.text():
            QMessageBox.warning(self, "Fehlende Eingabe", "Bitte geben Sie einen Betreff ein.")
            return
            
        if not self.content_edit.toPlainText():
            QMessageBox.warning(self, "Fehlende Eingabe", "Bitte geben Sie einen E-Mail-Inhalt ein.")
            return
            
        # Empfänger bestimmen
        recipient_ids = []
        team_id = None
        project_id = None
        
        if self.person_select_radio.isChecked():
            # Einzelne Personen auswählen
            for i in range(self.person_list.count()):
                item = self.person_list.item(i)
                if item.isSelected():
                    recipient_ids.append(item.data(Qt.UserRole))
                    
            if not recipient_ids:
                QMessageBox.warning(self, "Keine Empfänger", "Bitte wählen Sie mindestens einen Empfänger aus.")
                return
        
        if self.team_select_radio.isChecked():
            # Team auswählen
            if self.team_combo.currentIndex() >= 0:
                team_id = self.team_combo.currentData()
            else:
                QMessageBox.warning(self, "Kein Team", "Bitte wählen Sie ein Team aus.")
                return
        
        if self.project_select_radio.isChecked():
            # Projekt auswählen
            if self.project_combo.currentIndex() >= 0:
                project_id = self.project_combo.currentData()
            else:
                QMessageBox.warning(self, "Kein Projekt", "Bitte wählen Sie ein Projekt aus.")
                return
                
        # HTML-Inhalt vorbereiten
        html_content = None
        if self.html_radio.isChecked():
            html_content = self.content_edit.toPlainText()
            
        # Fortschrittsdialog anzeigen
        progress = QProgressDialog("Sende E-Mails...", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("E-Mail-Versand")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)
        
        # E-Mails senden
        stats = email_service.send_custom_email(
            subject=self.subject_edit.text(),
            text_content=self.content_edit.toPlainText(),
            html_content=html_content,
            recipient_ids=recipient_ids or None,
            team_id=team_id,
            project_id=project_id
        )
        
        progress.setValue(100)
        
        # Ergebnis anzeigen
        QMessageBox.information(
            self,
            "E-Mail-Versand abgeschlossen",
            f"Ergebnis des E-Mail-Versands:\n\n"
            f"Erfolgreich gesendet: {stats['success']}\n"
            f"Fehlgeschlagen: {stats['failed']}"
        )
        
        self.accept()
