"""
Teil 4 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für benutzerdefinierte E-Mails inklusive
Platzhalter-Toolbar für Personalisierung pro Empfänger.
"""
from uuid import UUID

from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressDialog,
    QPushButton,
    QTextEdit,
)
from PySide6.QtCore import Qt

from gui.api_client import email as email_api
from gui.email_to_users.base_email_dialog import BaseEmailDialog
from gui.email_to_users.shared_dialogs import show_email_send_result


# Verfügbare Platzhalter (deutsch). Server rendert sie pro Empfänger via Jinja2.
# Reihenfolge ist die Anzeige-Reihenfolge in der Toolbar.
_PLACEHOLDERS: list[tuple[str, str]] = [
    ("Vorname", "{{ vorname }}"),
    ("Nachname", "{{ nachname }}"),
    ("Name", "{{ name }}"),
    ("E-Mail", "{{ email }}"),
]


class CustomEmailDialog(BaseEmailDialog):
    """Dialog zum Senden personalisierter E-Mails an einzelne Empfänger.

    Personalisierung: Subject und Body können Platzhalter wie `{{ vorname }}`
    enthalten — der Server rendert sie pro Empfänger mit den jeweiligen Person-
    Werten. Klick auf einen Platzhalter-Button fügt den Token an der Cursor-
    Position des zuletzt fokussierten Eingabefelds ein (Subject oder Body).
    """

    def __init__(self, parent=None, project_id: UUID = None):
        super().__init__(parent, project_id)
        self.setWindowTitle("Benutzerdefinierte E-Mail senden")
        self.content_edit.setPlaceholderText(
            "E-Mail-Inhalt eingeben. Personalisierung über die Platzhalter-Buttons "
            "in der Format-Leiste — pro Empfänger werden die Platzhalter durch die "
            "individuellen Werte ersetzt."
        )

        # Last-focused-text-widget tracken: Klick auf einen Platzhalter-Button
        # fügt in das zuletzt fokussierte LineEdit/TextEdit ein. Default ist
        # der Body, damit Klicks vor dem ersten Fokus-Wechsel sinnvoll wirken.
        self._last_text_target: QLineEdit | QTextEdit = self.content_edit
        QApplication.instance().focusChanged.connect(self._on_focus_changed)

        self._add_placeholder_buttons()

        from tools.helper_functions import setup_form_help
        setup_form_help(self, "email_custom", add_help_button=True)

    def _on_focus_changed(self, _old, new):
        """Speichert das zuletzt fokussierte Text-Widget — als Insert-Ziel.

        Buttons und andere Widgets übergehen wir bewusst, damit das Klicken
        eines Platzhalter-Buttons das Insert-Ziel nicht überschreibt.
        """
        if isinstance(new, (QLineEdit, QTextEdit)):
            self._last_text_target = new

    def _add_placeholder_buttons(self):
        """Hängt die 4 Platzhalter-Buttons an die bestehende Format-Toolbar an."""
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.VLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        self.format_toolbar.addWidget(separator)

        label = QLabel("Platzhalter einfügen:")
        self.format_toolbar.addWidget(label)

        for caption, placeholder in _PLACEHOLDERS:
            btn = QPushButton(caption)
            btn.setToolTip(
                f"Fügt {placeholder} an der Cursor-Position des zuletzt "
                f"angeklickten Eingabefelds ein. Wird pro Empfänger ersetzt."
            )
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.clicked.connect(
                lambda _checked=False, ph=placeholder: self._insert_placeholder(ph)
            )
            self.format_toolbar.addWidget(btn)

    def _insert_placeholder(self, placeholder: str):
        """Fügt den Placeholder an der Cursor-Position des letzten Text-Widgets ein."""
        target = self._last_text_target
        if isinstance(target, QLineEdit):
            target.insert(placeholder)
            target.setFocus()
        elif isinstance(target, QTextEdit):
            target.insertPlainText(placeholder)
            target.setFocus()
        else:
            self.content_edit.insertPlainText(placeholder)
            self.content_edit.setFocus()

    def send_email(self):
        """Sendet die E-Mail."""
        if not self.subject_edit.text():
            QMessageBox.warning(self, "Fehlende Eingabe", "Bitte geben Sie einen Betreff ein.")
            return

        if not self.content_edit.toPlainText():
            QMessageBox.warning(self, "Fehlende Eingabe", "Bitte geben Sie einen E-Mail-Inhalt ein.")
            return

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

        progress = QProgressDialog("Sende E-Mails...", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("E-Mail-Versand")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(10)

        # E-Mails über Web-API senden — Server personalisiert pro Empfänger.
        stats = email_api.send_custom_email(
            subject=self.subject_edit.text(),
            text_content=self.content_edit.toPlainText(),
            html_content=self.content_edit.toHtml(),
            recipient_ids=recipient_ids,
        )

        progress.setValue(100)

        if show_email_send_result(self, stats):
            self.accept()