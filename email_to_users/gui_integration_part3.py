"""
Teil 3 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für Verfügbarkeitsanfragen.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QCheckBox, QGroupBox, QListWidget, QListWidgetItem,
    QProgressDialog, QMessageBox
)
from PySide6.QtCore import Qt

from pony.orm import db_session

from database.models import PlanPeriod

from .service import email_service


class AvailabilityRequestDialog(QDialog):
    """Dialog zum Senden von Verfügbarkeitsanfragen."""
    
    def __init__(self, plan_period_id, parent=None):
        """
        Initialisiert den Dialog.
        
        Args:
            plan_period_id: ID des Planungszeitraums
            parent: Übergeordnetes Widget
        """
        super().__init__(parent)
        self.plan_period_id = plan_period_id
        self.setWindowTitle("Verfügbarkeitsanfrage senden")
        self.setMinimumWidth(600)
        
        self.setup_ui()
        self.load_recipients()
        
    @db_session
    def setup_ui(self):
        """Erstellt die UI-Elemente."""
        layout = QVBoxLayout(self)
        
        # Planungszeitraum-Informationen
        plan_period = PlanPeriod[self.plan_period_id]
        
        info_text = (f"<h3>Verfügbarkeitsanfrage</h3>"
                    f"<p>Zeitraum: {plan_period.start.strftime('%d.%m.%Y')} - "
                    f"{plan_period.end.strftime('%d.%m.%Y')}</p>"
                    f"<p>Team: {plan_period.team.name}</p>"
                    f"<p>Deadline: {plan_period.deadline.strftime('%d.%m.%Y')}</p>")
        
        info_label = QLabel(info_text)
        info_label.setTextFormat(Qt.RichText)
        layout.addWidget(info_label)
        
        # Empfänger-Gruppe
        recipients_group = QGroupBox("Empfänger")
        recipients_layout = QVBoxLayout(recipients_group)
        
        self.all_recipients_check = QCheckBox("Alle Teammitglieder")
        self.all_recipients_check.setChecked(True)
        self.all_recipients_check.toggled.connect(self.toggle_recipient_list)
        
        self.recipient_list = QListWidget()
        self.recipient_list.setSelectionMode(QListWidget.MultiSelection)
        self.recipient_list.setEnabled(False)
        
        recipients_layout.addWidget(self.all_recipients_check)
        recipients_layout.addWidget(self.recipient_list)
        
        layout.addWidget(recipients_group)
        
        # Optionen
        options_group = QGroupBox("Optionen")
        options_layout = QVBoxLayout(options_group)
        
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("Basis-URL für Verfügbarkeitseingabe:"))
        self.url_edit = QLineEdit("http://localhost:8000/availability")
        url_layout.addWidget(self.url_edit)
        
        self.notes_edit = QTextEdit()
        self.notes_edit.setPlaceholderText("Zusätzliche Hinweise für die Mitarbeiter...")
        
        options_layout.addLayout(url_layout)
        options_layout.addWidget(QLabel("Hinweise:"))
        options_layout.addWidget(self.notes_edit)
        
        layout.addWidget(options_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.send_button = QPushButton("Senden")
        self.cancel_button = QPushButton("Abbrechen")
        
        self.send_button.clicked.connect(self.send_requests)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)
        
    @db_session
    def load_recipients(self):
        """Lädt die Empfänger in die Liste."""
        plan_period = PlanPeriod[self.plan_period_id]
        team = plan_period.team
        
        # Sammle alle Personen des Teams
        recipients = []
        for taa in team.team_actor_assigns:
            if (not taa.end or taa.end >= plan_period.start) and taa.start <= plan_period.end:
                if taa.person not in recipients:
                    recipients.append(taa.person)
        
        # Füge Empfänger zur Liste hinzu
        for person in recipients:
            item = QListWidgetItem(f"{person.full_name} ({person.email})")
            item.setData(Qt.UserRole, person.id)
            self.recipient_list.addItem(item)
    
    def toggle_recipient_list(self, checked):
        """Aktiviert/deaktiviert die Empfängerliste."""
        self.recipient_list.setEnabled(not checked)
        
        # Wähle alle Einträge aus, wenn "Alle Empfänger" aktiviert ist
        if checked:
            for i in range(self.recipient_list.count()):
                self.recipient_list.item(i).setSelected(True)
        else:
            for i in range(self.recipient_list.count()):
                self.recipient_list.item(i).setSelected(False)
    
    def send_requests(self):
        """Sendet die Verfügbarkeitsanfragen."""
        recipient_ids = []
        
        # Wenn "Alle Empfänger" aktiviert ist, werden keine IDs übergeben
        if not self.all_recipients_check.isChecked():
            for i in range(self.recipient_list.count()):
                item = self.recipient_list.item(i)
                if item.isSelected():
                    recipient_ids.append(item.data(Qt.UserRole))
        
        # Fortschrittsdialog anzeigen
        progress = QProgressDialog("Sende E-Mails...", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("E-Mail-Versand")
        progress.setWindowModality(Qt.WindowModal)
        progress.setValue(10)
        
        # E-Mails senden
        stats = email_service.send_availability_request(
            plan_period_id=self.plan_period_id,
            recipient_ids=recipient_ids or None,
            url_base=self.url_edit.text() if self.url_edit.text() else None,
            notes=self.notes_edit.toPlainText() if self.notes_edit.toPlainText() else None
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
