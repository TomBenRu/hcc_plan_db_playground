"""
Teil 5 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für Massen-E-Mails an mehrere Nutzer.
"""
import os
from uuid import UUID
import datetime

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QGroupBox, QListWidget, QListWidgetItem, QProgressDialog,
    QMessageBox, QFileDialog, QTabWidget, QWidget, QFormLayout, QRadioButton, QComboBox, QCheckBox, QMenu, QApplication,
    QScrollArea
)
from PySide6.QtGui import QFont, QTextCharFormat
from PySide6.QtCore import Qt

from configuration.project_paths import curr_user_path_handler
from database import db_services, schemas
from email_to_users.service import email_service
from email_to_users.sender import EmailSender
from gui.email_to_users.shared_dialogs import TeamAssignmentDateDialog
from tools.helper_functions import date_to_string


class BulkEmailDialog(QDialog):
    """Dialog zum Senden von benutzerdefinierten E-Mails."""

    def __init__(self, parent=None, project_id: UUID = None):
        """Initialisiert den Dialog."""
        super().__init__(parent)
        self.setWindowTitle("Benutzerdefinierte E-Mail senden")
        self.setMinimumWidth(700)
        self.setMinimumHeight(600)

        self.project_id = project_id
        self.attachment_files = set()
        self.path_to_excel_export = curr_user_path_handler.get_config().excel_output_path

        self._setup_ui()
        self.load_recipients()

    def _setup_ui(self):
        """Erstellt die UI-Elemente."""

        # Methode zum Anpassen der Höhe basierend auf der Scrollbar-Sichtbarkeit
        def adjust_scroll_height():
            # Prüfen, ob die Scrollbar einen gültigen Bereich hat (d.h. ob sie wirklich benötigt wird)
            # alle Layout-Events verarbeiten, damit die Scrollbar angezeigt wird, falls nötig
            QApplication.processEvents()
            scrollbar = self.attachments_scroll.horizontalScrollBar()
            has_scrollbar = scrollbar.minimum() < scrollbar.maximum()
            scrollbar_height = scrollbar.height() if has_scrollbar else 0
            self.attachments_scroll.setFixedHeight(35 + scrollbar_height)  # Basishöhe + Scrollbar-Höhe

        layout = QVBoxLayout(self)

        # E-Mail-Kopf
        header_group = QGroupBox("E-Mail-Kopf")
        header_layout = QFormLayout(header_group)

        self.subject_edit = QLineEdit()
        header_layout.addRow("Betreff:", self.subject_edit)

        layout.addWidget(header_group)

        # Empfänger-Gruppe
        recipients_group = QGroupBox("Empfänger (To/CC/BCC per Rechtsklick wählbar)")
        recipients_layout = QVBoxLayout(recipients_group)

        # Team-Auswahl
        selection_layout = QHBoxLayout()

        self.team_combo = QComboBox()
        self.team_combo.currentIndexChanged.connect(self.filter_persons)
        self.team_assignment_button = QPushButton(date_to_string(datetime.date.today()))
        self.team_assignment_date: datetime.date = datetime.date.today()
        self.team_assignment_button.clicked.connect(self.show_team_assignment_date_dialog)
        self.inclusive_none_team_check = QCheckBox("Keinem Team zugeordnete Personen einbeziehen")
        self.inclusive_none_team_check.setChecked(False)
        self.inclusive_none_team_check.toggled.connect(self.filter_persons)

        selection_layout.addWidget(QLabel("Filter für Team:"))
        selection_layout.addWidget(self.team_combo)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(QLabel("Zuweisungsdatum:"))
        selection_layout.addWidget(self.team_assignment_button)
        selection_layout.addSpacing(20)
        selection_layout.addWidget(self.inclusive_none_team_check)
        selection_layout.addStretch(1)

        # Anhänge
        self.attachments_layout = QHBoxLayout()
        self.attachments_layout.setSpacing(5)  # Kleiner Abstand zwischen den Anhängen
        self.attachments_layout.setContentsMargins(0, 0, 0, 0)

        # QScrollArea für horizontales Scrollen bei vielen Anhängen
        self.attachments_scroll = QScrollArea()
        self.attachments_scroll.setWidgetResizable(True)
        self.attachments_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.attachments_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.attachments_scroll.horizontalScrollBar().rangeChanged.connect(adjust_scroll_height)
        adjust_scroll_height()

        # Container-Widget für das Layout
        self.attachments_container = QWidget()
        self.attachments_container.setLayout(self.attachments_layout)
        self.attachments_scroll.setWidget(self.attachments_container)

        # Anhänge-Button
        self.attachments_button = QPushButton("Anhänge hinzufügen")
        self.attachments_button.clicked.connect(self.add_attachments)

        # Layout für Anhänge-Bereich und Button
        self.attachments_area = QVBoxLayout()
        self.attachments_area.addWidget(self.attachments_scroll)
        self.attachments_area.addWidget(self.attachments_button)

        # Personenliste
        self.person_list = QListWidget()
        self.person_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        # Schriftfarbe selektierter Einträge auf grün setzen
        self.person_list.setStyleSheet("""
            QListWidget::item:selected { background-color: rgba(17, 199, 0, 50); }
        """)
        
        # Rechtsklick-Menü für Empfängertyp (To, CC, BCC)
        self.person_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.person_list.customContextMenuRequested.connect(self.show_context_menu)
        
        # Konstanten für benutzerdefinierte Datenrollen
        self.RECIPIENT_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1

        recipients_layout.addLayout(selection_layout)
        recipients_layout.addWidget(self.person_list)

        layout.addWidget(recipients_group)

        # Buttons für alle Empfänger aus-/abwählen
        select_all_button = QPushButton("Alle auswählen")
        select_all_button.clicked.connect(self.select_all_persons)
        deselect_all_button = QPushButton("Alle abwählen")
        deselect_all_button.clicked.connect(self.deselect_all_persons)
        button_layout = QHBoxLayout()
        button_layout.addWidget(select_all_button)
        button_layout.addWidget(deselect_all_button)
        recipients_layout.addLayout(button_layout)

        # E-Mail-Inhalt
        content_group = QGroupBox("E-Mail-Inhalt")
        content_layout = QVBoxLayout(content_group)

        self.content_edit = QTextEdit()
        self.content_edit.setAcceptRichText(True)  # Erlaubt Rich-Text-Bearbeitung
        self.content_edit.setPlaceholderText(
            "E-Mail-Inhalt hier eingeben... (Personalisierung möglich mit {{ f_name }}, {{ l_name }}, {{ full_name }}, {{ email }})")

        # Formatierungsleiste hinzufügen
        self.format_toolbar = QHBoxLayout()
        bold_button = QPushButton("B")
        bold_font = QFont("Arial", 10)
        bold_font.setBold(True)
        bold_button.setFont(bold_font)
        bold_button.setFixedSize(30, 25)
        bold_button.clicked.connect(lambda: self.format_text("bold"))

        italic_button = QPushButton("I")
        italic_font = QFont("Arial", 10)
        italic_font.setItalic(True)
        italic_button.setFont(italic_font)
        italic_button.setFixedSize(30, 25)
        italic_button.clicked.connect(lambda: self.format_text("italic"))

        underline_button = QPushButton("U")
        underline_font = QFont("Arial", 10)
        underline_font.setUnderline(True)
        underline_button.setFont(underline_font)
        underline_button.setFixedSize(30, 25)
        underline_button.clicked.connect(lambda: self.format_text("underline"))

        self.format_toolbar.addWidget(bold_button)
        self.format_toolbar.addWidget(italic_button)
        self.format_toolbar.addWidget(underline_button)
        self.format_toolbar.addStretch(1)

        # Toolbar und Editor zum Layout hinzufügen
        content_layout.addLayout(self.format_toolbar)
        content_layout.addWidget(self.content_edit)

        layout.addWidget(content_group)

        layout.addLayout(self.attachments_area)

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
            item = QListWidgetItem(f"[To] {person.full_name} ({person.email})")
            item.setData(Qt.ItemDataRole.UserRole, person)
            # Standardtyp "To" setzen
            item.setData(self.RECIPIENT_TYPE_ROLE, "To")
            self.person_list.addItem(item)

        # Lade Teams
        teams = sorted(db_services.Team.get_all_from__project(self.project_id), key=lambda x: x.name)
        self.team_combo.addItem("Alle Teams", None)
        for team in teams:
            self.team_combo.addItem(team.name, team.id)

    def filter_persons(self):
        """Filtert die Personenliste nach dem ausgewählten Team."""
        selected_team_id = self.team_combo.currentData()
        if selected_team_id is None:
            # Kein Team ausgewählt, also alle Personen anzeigen
            for i in range(self.person_list.count()):
                item = self.person_list.item(i)
                item.setSelected(False)
                person: schemas.PersonShow = item.data(Qt.ItemDataRole.UserRole)
                assigned_to_team_on_date = [taa for taa in person.team_actor_assigns
                                            if taa.start <= self.team_assignment_date <
                                            (taa.end or self.team_assignment_date + datetime.timedelta(days=1))]
                if not self.inclusive_none_team_check.isChecked() and not assigned_to_team_on_date:
                    self.person_list.item(i).setHidden(True)
                    continue
                self.person_list.item(i).setHidden(False)
        else:
            # Nur Personen des ausgewählten Teams am gewählten Datum anzeigen
            for i in range(self.person_list.count()):
                item = self.person_list.item(i)
                item.setSelected(False)
                person = item.data(Qt.ItemDataRole.UserRole)
                assigned_to_team_on_date = [taa for taa in person.team_actor_assigns
                                            if taa.start <= self.team_assignment_date <
                                            (taa.end or self.team_assignment_date + datetime.timedelta(days=1))]
                if (assigned_to_team_on_date
                        and self.team_combo.currentData() in [taa.team.id for taa in assigned_to_team_on_date]):
                    item.setHidden(False)
                elif not assigned_to_team_on_date and self.inclusive_none_team_check.isChecked():
                    item.setHidden(False)
                else:
                    item.setHidden(True)

    def show_team_assignment_date_dialog(self):
        """Zeigt den Dialog zum Zuweisen von Teams an."""
        dialog = TeamAssignmentDateDialog(self, self.team_assignment_date)
        if dialog.exec_():
            self.team_assignment_date = dialog.calendar.selectedDate().toPython()
            self.team_assignment_button.setText(date_to_string(self.team_assignment_date))
            self.filter_persons()

    def select_all_persons(self):
        """Wählt alle Personen aus."""
        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            if not item.isHidden():
                item.setSelected(True)

    def deselect_all_persons(self):
        """Deselects all persons."""
        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            item.setSelected(False)

    def add_attachments(self):
        """Öffnet einen Dateidialog und fügt ausgewählte Dateien als Anhänge hinzu"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Anhänge auswählen", self.path_to_excel_export, "Alle Dateien (*)")

        for file_path in files:
            file_name = os.path.basename(file_path)
            if file_path in self.attachment_files:
                continue
            self.add_attachment_widget(file_name, file_path)
            self.attachment_files.add(file_path)

    def add_attachment_widget(self, file_name, file_path):
        """Erstellt ein Widget für einen Anhang und fügt es zum Layout hinzu"""
        # Container für Dateiname und Entfernen-Button
        attachment_widget = QWidget()
        attachment_layout = QHBoxLayout(attachment_widget)
        attachment_layout.setContentsMargins(2, 2, 2, 2)
        attachment_widget.setStyleSheet("background-color: rgba(17, 199, 0, 25); border-radius: 5px;")

        # Dateiname-Label
        name_label = QLabel(file_name)
        name_label.setToolTip(file_path)  # Vollständiger Pfad als Tooltip

        # Entfernen-Button
        remove_button = QPushButton("×")
        remove_button.setFixedSize(20, 20)
        remove_button.setStyleSheet("border: none; background-color: rgba(255, 0, 0, 50);")
        remove_button.setToolTip("Anhang entfernen")
        remove_button.clicked.connect(lambda checked, w=attachment_widget, p=file_path: self.remove_attachment(w, p))

        # Komponenten zum Layout hinzufügen
        attachment_layout.addWidget(name_label)
        attachment_layout.addWidget(remove_button)

        # Widget zum Anhänge-Layout hinzufügen
        self.attachments_layout.addWidget(attachment_widget)

    def remove_attachment(self, widget, file_path):
        """Entfernt einen Anhang aus dem Layout und der internen Liste"""
        # Entferne Widget aus dem Layout
        self.attachments_layout.removeWidget(widget)
        widget.deleteLater()
        self.attachment_files.remove(file_path)

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
        to_recipients = []
        cc_recipients = []
        bcc_recipients = []

        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            if item.isSelected():
                person = item.data(Qt.ItemDataRole.UserRole)
                # Empfängertyp direkt aus dem Item lesen
                recipient_type = item.data(self.RECIPIENT_TYPE_ROLE)
                
                if recipient_type == "To":
                    to_recipients.append(person)
                elif recipient_type == "CC":
                    cc_recipients.append(person)
                elif recipient_type == "BCC":
                    bcc_recipients.append(person)

        if not (to_recipients or cc_recipients or bcc_recipients):
            QMessageBox.warning(self, "Keine Empfänger", "Bitte wählen Sie mindestens einen Empfänger aus.")
            return

        # Fortschrittsdialog anzeigen
        progress = QProgressDialog("Sende E-Mail...", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("E-Mail-Versand")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(10)

        # E-Mail senden
        stats = email_service.send_bulk_email(
            subject=self.subject_edit.text(),
            text_content=self.content_edit.toPlainText(),
            html_content=self.content_edit.toHtml(),
            recipients=to_recipients,
            cc=cc_recipients,
            bcc=bcc_recipients,
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

    def format_text(self, format_type):
        """Formatiert den ausgewählten Text."""
        cursor = self.content_edit.textCursor()
        if not cursor.hasSelection():
            return

        if format_type == "bold":
            if cursor.charFormat().fontWeight() == QFont.Bold:
                cursor.setCharFormat(QTextCharFormat())
            else:
                char_format = QTextCharFormat()
                char_format.setFontWeight(QFont.Bold)
                cursor.mergeCharFormat(char_format)
        elif format_type == "italic":
            char_format = QTextCharFormat()
            char_format.setFontItalic(not cursor.charFormat().fontItalic())
            cursor.mergeCharFormat(char_format)
        elif format_type == "underline":
            char_format = QTextCharFormat()
            char_format.setFontUnderline(not cursor.charFormat().fontUnderline())
            cursor.mergeCharFormat(char_format)

        self.content_edit.setTextCursor(cursor)
