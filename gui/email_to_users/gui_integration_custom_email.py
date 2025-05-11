"""
Teil 4 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für benutzerdefinierte E-Mails.
"""
from uuid import UUID

from PySide6.QtWidgets import QMessageBox, QProgressDialog
from PySide6.QtCore import Qt

from email_to_users.service import email_service
from gui.email_to_users.base_email_dialog import BaseEmailDialog


class CustomEmailDialog(BaseEmailDialog):
    """Dialog zum Senden von benutzerdefinierten E-Mails."""
    
    def __init__(self, parent=None, project_id: UUID = None):
        """Initialisiert den Dialog."""
        super().__init__(parent, project_id)
        self.setWindowTitle("Benutzerdefinierte E-Mail senden")
        self.content_edit.setPlaceholderText(
            "E-Mail-Inhalt hier eingeben... "
            "(Personalisierung möglich mit {{ f_name }}, {{ l_name }}, {{ full_name }}, {{ email }})")
    
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
        recipients = []

        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            if item.isSelected():
                recipients.append(item.data(Qt.ItemDataRole.UserRole))

        if not recipients:
            QMessageBox.warning(self, "Keine Empfänger", "Bitte wählen Sie mindestens einen Empfänger aus.")
            return
            
        # Fortschrittsdialog anzeigen
        progress = QProgressDialog("Sende E-Mails...", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("E-Mail-Versand")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(10)
        
        # E-Mails senden
        stats = email_service.send_custom_email(
            subject=self.subject_edit.text(),
            text_content=self.content_edit.toPlainText(),
            html_content=self.content_edit.toHtml(),
            recipients=recipients or None,
            attachments=[{'path': file_path} for file_path in self.attachment_files]
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
