"""
Teil 5 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für Massen-E-Mails an mehrere Nutzer.
"""
from uuid import UUID

from PySide6.QtWidgets import QMessageBox, QProgressDialog, QMenu
from PySide6.QtCore import Qt

from gui.api_client import email as email_api
from gui.email_to_users.base_email_dialog import BaseEmailDialog
from gui.email_to_users.shared_dialogs import show_email_send_result


class BulkEmailDialog(BaseEmailDialog):
    """Dialog zum Senden von Massen-E-Mails mit To/CC/BCC-Auswahl."""

    def __init__(self, parent=None, project_id: UUID = None):
        """Initialisiert den Dialog."""
        super().__init__(parent, project_id)
        self.setWindowTitle("Benutzerdefinierte E-Mail senden")

        self.content_edit.setPlaceholderText(
            "E-Mail-Inhalt hier eingeben...")
        
        # Konstante für benutzerdefinierte Datenrolle
        self.RECIPIENT_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1
        
        # Rechtsklick-Menü für Empfängertyp (To, CC, BCC)
        self.recipients_group.setTitle("Empfänger (To/CC/BCC per Rechtsklick wählbar)")
        self.person_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.person_list.customContextMenuRequested.connect(self.show_context_menu)
        
        # Standardtyp "To" für alle Einträge setzen
        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            item.setData(self.RECIPIENT_TYPE_ROLE, "To")
            # Präfix hinzufügen
            current_text = item.text()
            item.setText(f"[To] {current_text}")
        
        # Override F1 Help für spezifische HTML-Datei
        from tools.helper_functions import setup_form_help
        setup_form_help(self, "email_bulk", add_help_button=True)

    def show_context_menu(self, position):
        """Zeigt das Kontextmenü für die Personenliste an."""
        # Element unter dem Cursor finden
        item = self.person_list.itemAt(position)
        if not item:
            return

        context_menu = QMenu(self)
        to_action = context_menu.addAction("To")
        cc_action = context_menu.addAction("CC")
        bcc_action = context_menu.addAction("BCC")
        
        # Kontextmenü anzeigen und Aktion abrufen
        action = context_menu.exec(self.person_list.mapToGlobal(position))
        
        if action:
            # Empfängertyp für das Element unter dem Cursor setzen
            recipient_type = None
            if action == to_action:
                recipient_type = "To"
            elif action == cc_action:
                recipient_type = "CC"
            elif action == bcc_action:
                recipient_type = "BCC"
                
            if recipient_type:
                # Typ direkt im Item speichern
                item.setData(self.RECIPIENT_TYPE_ROLE, recipient_type)
                
                # Visuelles Feedback durch Präfix im Listeneintrag
                current_text = item.text()
                if current_text.startswith("[To] ") or current_text.startswith("[CC] ") or current_text.startswith("[BCC] "):
                    # Präfix entfernen, wenn bereits vorhanden
                    text_without_prefix = current_text.split("] ", 1)[1]
                    item.setText(f"[{recipient_type}] {text_without_prefix}")
                else:
                    item.setText(f"[{recipient_type}] {current_text}")

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
        to_ids = []
        cc_ids = []
        bcc_ids = []

        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            if item.isSelected():
                person = item.data(Qt.ItemDataRole.UserRole)
                recipient_type = item.data(self.RECIPIENT_TYPE_ROLE)

                if recipient_type == "To":
                    to_ids.append(person.id)
                elif recipient_type == "CC":
                    cc_ids.append(person.id)
                elif recipient_type == "BCC":
                    bcc_ids.append(person.id)

        if not (to_ids or cc_ids or bcc_ids):
            QMessageBox.warning(self, "Keine Empfänger", "Bitte wählen Sie mindestens einen Empfänger aus.")
            return

        if self.attachment_files:
            QMessageBox.warning(
                self,
                "Anhänge nicht unterstützt",
                "Anhänge werden im aktuellen Versand-Pfad nicht unterstützt und werden ignoriert.",
            )

        # Fortschrittsdialog anzeigen
        progress = QProgressDialog("Sende E-Mail...", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("E-Mail-Versand")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(10)

        # E-Mail ueber Web-API senden (Server haelt SMTP-Konfig)
        stats = email_api.send_bulk_email(
            subject=self.subject_edit.text(),
            text_content=self.content_edit.toPlainText(),
            html_content=self.content_edit.toHtml(),
            recipient_ids=to_ids,
            cc_ids=cc_ids,
            bcc_ids=bcc_ids,
        )

        progress.setValue(100)

        # Ergebnis anzeigen
        if show_email_send_result(self, stats):
            self.accept()
