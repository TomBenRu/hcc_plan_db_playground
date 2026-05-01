"""
Teil 4 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für benutzerdefinierte E-Mails.
"""
from uuid import UUID

from PySide6.QtWidgets import QMessageBox, QProgressDialog
from PySide6.QtCore import Qt

from gui.api_client import email as email_api
from gui.email_to_users.base_email_dialog import BaseEmailDialog
from gui.email_to_users.shared_dialogs import show_email_send_result


class CustomEmailDialog(BaseEmailDialog):
    """Dialog zum Senden von benutzerdefinierten E-Mails."""
    
    def __init__(self, parent=None, project_id: UUID = None):
        """Initialisiert den Dialog."""
        super().__init__(parent, project_id)
        self.setWindowTitle("Benutzerdefinierte E-Mail senden")
        self.content_edit.setPlaceholderText(
            "E-Mail-Inhalt hier eingeben... "
            "(Personalisierung möglich mit {{ f_name }}, {{ l_name }}, {{ full_name }}, {{ email }})")
        
        # Override F1 Help für spezifische HTML-Datei
        from tools.helper_functions import setup_form_help
        setup_form_help(self, "email_custom", add_help_button=True)
    
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

        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            if item.isSelected():
                person = item.data(Qt.ItemDataRole.UserRole)
                recipient_ids.append(person.id)

        if not recipient_ids:
            QMessageBox.warning(self, "Keine Empfänger", "Bitte wählen Sie mindestens einen Empfänger aus.")
            return

        if self.attachment_files:
            QMessageBox.warning(
                self,
                "Anhänge nicht unterstützt",
                "Anhänge werden im aktuellen Versand-Pfad nicht unterstützt und werden ignoriert.",
            )

        # Fortschrittsdialog anzeigen
        progress = QProgressDialog("Sende E-Mails...", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("E-Mail-Versand")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(10)

        # E-Mails ueber Web-API senden (Server haelt SMTP-Konfig)
        stats = email_api.send_custom_email(
            subject=self.subject_edit.text(),
            text_content=self.content_edit.toPlainText(),
            html_content=self.content_edit.toHtml(),
            recipient_ids=recipient_ids,
        )
        
        progress.setValue(100)
        
        # Ergebnis anzeigen
        if show_email_send_result(self, stats):
            self.accept()
