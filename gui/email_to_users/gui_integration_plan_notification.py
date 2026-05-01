"""
Teil 2 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für Einsatzplan-Benachrichtigungen.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QListWidget, QListWidgetItem,
    QPushButton, QCheckBox, QGroupBox, QProgressDialog
)
from PySide6.QtCore import Qt

from database import db_services
from gui.api_client import email as email_api
from gui.email_to_users.shared_dialogs import show_email_send_result
from tools.helper_functions import setup_form_help


class PlanNotificationDialog(QDialog):
    """Dialog zum Senden von Einsatzplan-Benachrichtigungen."""
    
    def __init__(self, parent=None):
        """
        Initialisiert den Dialog.
        
        Args:
            plan_id: ID des Plans
            parent: Übergeordnetes Widget
        """
        super().__init__(parent)
        self.setWindowTitle("Einsatzplan-Benachrichtigung senden")
        self.setMinimumWidth(600)
        
        self.setup_ui()
        
        # F1 Help Integration
        setup_form_help(self, "email_plan_notification", add_help_button=True)

    def setup_ui(self):
        """Erstellt die UI-Elemente."""
        layout = QVBoxLayout(self)
        
        # info_text = (f"<h3>Einsatzplan: {plan.name}</h3>"
        #             f"<p>Zeitraum: {plan_period.start.strftime('%d.%m.%Y')} - "
        #             f"{plan_period.end.strftime('%d.%m.%Y')}</p>"
        #             f"<p>Team: {plan_period.team.name}</p>")
        
        info_label = QLabel()
        info_label.setTextFormat(Qt.RichText)
        layout.addWidget(info_label)
        
        # Empfänger-Gruppe
        recipients_group = QGroupBox("Empfänger")
        recipients_layout = QVBoxLayout(recipients_group)
        
        self.all_recipients_check = QCheckBox("Alle im Plan eingetragenen Mitarbeiter")
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
        
        self.include_attachments_check = QCheckBox("Einsatzplan als Anhang mitschicken")
        self.include_attachments_check.setChecked(True)
        
        options_layout.addWidget(self.include_attachments_check)
        
        layout.addWidget(options_group)
        
        # Buttons
        button_layout = QHBoxLayout()
        
        self.send_button = QPushButton("Senden")
        self.cancel_button = QPushButton("Abbrechen")
        
        self.send_button.clicked.connect(self.send_notifications)
        self.cancel_button.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.send_button)
        button_layout.addWidget(self.cancel_button)
        
        layout.addLayout(button_layout)

    def load_recipients(self):
        """Lädt die Empfänger in die Liste."""
        plan = db_services.Plan.get(self.plan_id)
        
        # Sammle alle Personen, die in dem Plan eingetragen sind
        recipients = set()
        for appointment in plan.appointments:
            for avail_day in appointment.avail_days:
                recipients.add(avail_day.actor_plan_period.person)
        
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
    
    def send_notifications(self):
        """Sendet die Benachrichtigungen."""
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
        
        # E-Mails ueber Web-API senden (Server haelt SMTP-Konfig)
        stats = email_api.send_plan_notification(
            plan_id=self.plan_id,
            recipient_ids=recipient_ids or None,
            include_attachments=self.include_attachments_check.isChecked(),
        )
        
        progress.setValue(100)
        
        # Ergebnis anzeigen
        if show_email_send_result(self, stats):
            self.accept()
