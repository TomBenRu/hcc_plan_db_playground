"""
Teil 4 der GUI-Integration für die E-Mail-Funktionalität.
Enthält den Dialog für benutzerdefinierte E-Mails.
"""
import datetime
import os
from uuid import UUID

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QTextEdit,
    QPushButton, QComboBox, QCheckBox, QGroupBox, QFormLayout,
    QListWidget, QListWidgetItem, QProgressDialog, QMessageBox, QCalendarWidget, QDialogButtonBox, QScrollArea, QWidget,
    QFileDialog, QApplication
)
from PySide6.QtCore import Qt, QDate

from configuration.project_paths import curr_user_path_handler
from database import db_services
from email_to_users.service import email_service
from tools.helper_functions import date_to_string


class TeamAssignmentDateDialog(QDialog):
    def __init__(self, parent: 'CustomEmailDialog', current_date: datetime.date | None = None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Team-Zuweisungsdatum")
        self.setMinimumWidth(300)
        self.current_date = current_date

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        self.calendar = QCalendarWidget()
        layout.addWidget(self.calendar)
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        if self.current_date:
            self.calendar.setSelectedDate(QDate(self.current_date.year, self.current_date.month, self.current_date.day))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)


class CustomEmailDialog(QDialog):
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
        recipients_group = QGroupBox("Empfänger")
        recipients_layout = QVBoxLayout(recipients_group)

        # Team-Auswahl
        selection_layout = QHBoxLayout()
        
        self.team_combo = QComboBox()
        self.team_combo.currentIndexChanged.connect(self.filter_persons)
        self.team_assignment_button = QPushButton(date_to_string(datetime.date.today()))
        self.team_assignment_date: datetime.date = datetime.date.today()
        self.team_assignment_button.clicked.connect(self.show_team_assignment_date_dialog)
        self.inclusive_none_team_check = QCheckBox("Keinem Team zugeordnete Teammitglieder einbeziehen")
        self.inclusive_none_team_check.setChecked(False)
        self.inclusive_none_team_check.toggled.connect(self.filter_persons)
        
        selection_layout.addWidget(QLabel("Filter fürTeam:"))
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
        self.content_edit.setPlaceholderText(
            "E-Mail-Inhalt hier eingeben... (Personalisierung möglich mit {name}, {email})")
        
        content_layout.addLayout(radio_layout)
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
            item = QListWidgetItem(f"{person.full_name} ({person.email})")
            item.setData(Qt.ItemDataRole.UserRole, person.id)
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
                person_id = item.data(Qt.ItemDataRole.UserRole)
                person = db_services.Person.get(person_id)
                assigned_to_team_on_date = [taa for taa in person.team_actor_assigns
                                            if taa.start <= self.team_assignment_date <
                                            (taa.end or self.team_assignment_date + datetime.timedelta(days=1))]
                if not self.inclusive_none_team_check.isChecked()and not assigned_to_team_on_date:
                    self.person_list.item(i).setHidden(True)
                    continue
                self.person_list.item(i).setHidden(False)
        else:
            # Nur Personen des ausgewählten Teams am gewählten Datum anzeigen
            for i in range(self.person_list.count()):
                item = self.person_list.item(i)
                person_id = item.data(Qt.ItemDataRole.UserRole)
                person = db_services.Person.get(person_id)
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

    def toggle_content_type(self, checked):
        """Wechselt zwischen Plaintext und HTML."""
        if self.plain_radio.isChecked() and self.html_radio.isChecked():
            # Stelle sicher, dass immer mindestens eine Option ausgewählt ist
            if self.sender() == self.plain_radio:
                self.html_radio.setChecked(False)
            else:
                self.plain_radio.setChecked(False)

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

        for i in range(self.person_list.count()):
            item = self.person_list.item(i)
            if item.isSelected():
                recipient_ids.append(item.data(Qt.ItemDataRole.UserRole))

        if not recipient_ids:
            QMessageBox.warning(self, "Keine Empfänger", "Bitte wählen Sie mindestens einen Empfänger aus.")
            return
                
        # HTML-Inhalt vorbereiten
        html_content = None
        if self.html_radio.isChecked():
            html_content = self.content_edit.toPlainText()
            
        # Fortschrittsdialog anzeigen
        progress = QProgressDialog("Sende E-Mails...", "Abbrechen", 0, 100, self)
        progress.setWindowTitle("E-Mail-Versand")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setValue(10)
        
        # E-Mails senden
        stats = email_service.send_custom_email(
            subject=self.subject_edit.text(),
            text_content=self.content_edit.toPlainText(),
            html_content=html_content,
            recipient_ids=recipient_ids or None,
            team_id=team_id,
            project_id=project_id,
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
