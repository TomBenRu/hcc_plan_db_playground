"""
Dialog für Employee Event Details - Create/Update/Delete.

Unterstützt sowohl das Erstellen neuer Events als auch die Bearbeitung bestehender Events
mit vollständiger Zeitfeld-Integration und Service-Layer-Anbindung.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import UUID

from PySide6.QtCore import Qt, QDateTime, QDate, QTime
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QTextEdit, QDateEdit, QTimeEdit, QGroupBox,
    QDialogButtonBox, QMessageBox, QPushButton, QCheckBox
)

from commands import command_base_classes
from configuration.general_settings import general_settings_handler
from database import db_services, schemas
from employee_event.db_commands import event_commands
from employee_event.schemas import employee_event_schemas
from employee_event import EmployeeEventService, EventDetail, ErrorResponseSchema
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import date_to_string, time_to_string

logger = logging.getLogger(__name__)


class DlgEmployeeEventDetails(QDialog):
    """
    Dialog für Employee Event Details.
    
    Features:
    - Create/Update/Delete von Employee Events
    - Zeitfeld-Integration mit Start/End DateTime
    - Team- und Kategorie-Auswahl
    - Teilnehmer-Management
    - Service-Layer-Integration
    - Vollständige Validierung
    """

    def __init__(self, parent: QWidget, project_id: UUID, event_id: Optional[UUID] = None):
        super().__init__(parent=parent)
        
        self.project_id = project_id
        self.event_id = event_id
        self.db_service = EmployeeEventService()

        self.controller = command_base_classes.ContrExecUndoRedo()
        
        # Daten-Cache
        self.current_event: Optional[EventDetail] = None
        self.teams_cache: List[schemas.Team] = []
        self.categories_cache: List[str] = []
        self.persons_cache: list[schemas.Person] = []
        self._current_participants: List[schemas.Person] = []  # Cache für Teilnehmer
        # self._current_participants: List[UUID] = []äää  # Cache für Teilnehmer-IDs
        
        # Modus-Bestimmung
        self.is_edit_mode = event_id is not None
        self.is_new_mode = not self.is_edit_mode
        
        self._setup_ui()
        self._setup_data()
        self._setup_connections()
        
        # Event laden wenn Edit-Modus
        if self.is_edit_mode:
            self._load_event()
        else:
            self._setup_defaults()
            
        logger.info(f"Employee Event Details Dialog initialized - Mode: {'Edit' if self.is_edit_mode else 'New'}")

    def _setup_ui(self):
        """Erstellt das komplette UI-Layout."""
        # Window-Konfiguration
        title = self.tr("Edit Event") if self.is_edit_mode else self.tr("New Event")
        self.setWindowTitle(title)
        self.setMinimumSize(500, 800)
        self.setModal(True)
        
        # Dark Theme Styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2d2d2d;
                color: white;
            }
            QLabel {
                color: white;
            }
            QLineEdit, QTextEdit, QDateTimeEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                padding: 0px;
            }
            QLineEdit:focus, QTextEdit:focus, QDateTimeEdit:focus {
                border: 2px solid #006d6d;
            }
            QGroupBox {
                color: #006d6d;
                font-weight: bold;
                border: 2px solid #555555;
                border-radius: 5px;
                margin: 10px 0px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)

        # Haupt-Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(20, 20, 20, 20)
        self.layout.setSpacing(15)

        # Header-Bereich
        self._setup_header()

        # Form-Bereich
        self._setup_form_area()

        # Zeitfelder-Bereich
        self._setup_datetime_area()

        # Zuordnungen-Bereich
        self._setup_assignments_area()

        # Options-Bereich (für Edit-Modus)
        if self.is_edit_mode:
            self._setup_options_area()

        # Button-Bereich
        self._setup_button_area()

    def _setup_header(self):
        """Erstellt den Header-Bereich."""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Icon + Titel
        icon_label = QLabel("📝")
        icon_label.setStyleSheet("font-size: 24px;")
        
        title_text = self.tr("Event Details")
        subtitle_text = self.tr("Edit existing event") if self.is_edit_mode else self.tr("Create new event")
        
        title_label = QLabel(f"<b>{title_text}</b><br><small>{subtitle_text}</small>")
        title_label.setStyleSheet("color: white; font-size: 14px;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.layout.addLayout(header_layout)

    def _setup_form_area(self):
        """Erstellt den Haupt-Form-Bereich."""
        form_group = QGroupBox(self.tr("General Information"))
        form_layout = QFormLayout(form_group)
        form_layout.setContentsMargins(15, 20, 15, 15)
        form_layout.setSpacing(10)

        # Titel
        self.le_title = QLineEdit()
        self.le_title.setPlaceholderText(self.tr("Enter event title..."))
        self.le_title.setMaxLength(40)  # Database constraint
        form_layout.addRow(self.tr("Title:"), self.le_title)

        # Beschreibung
        self.te_description = QTextEdit()
        self.te_description.setPlaceholderText(self.tr("Enter event description..."))
        self.te_description.setMaximumHeight(100)
        form_layout.addRow(self.tr("Description:"), self.te_description)

        self.layout.addWidget(form_group)

    def _setup_datetime_area(self):
        """Erstellt den DateTime-Bereich mit getrennten Datum- und Zeit-Feldern."""
        datetime_group = QGroupBox(self.tr("Date and Time"))
        datetime_layout = QFormLayout(datetime_group)
        datetime_layout.setContentsMargins(15, 15, 15, 30)
        datetime_layout.setSpacing(15)

        # Datum/Zeit-Konfiguration basierend auf Settings
        date_format_settings = general_settings_handler.get_general_settings().date_format_settings
        
        # Datum-Format basierend auf Einstellungen bestimmen
        if date_format_settings.format == "DD.MM.YYYY":
            date_display_format = "dd.MM.yyyy"
        elif date_format_settings.format == "MM/DD/YYYY":
            date_display_format = "MM/dd/yyyy"
        elif date_format_settings.format == "YYYY-MM-DD":
            date_display_format = "yyyy-MM-dd"
        else:
            date_display_format = "dd.MM.yyyy"  # Fallback
        
        # === START SECTION ===
        start_label = QLabel(self.tr("Start:"))
        start_label.setStyleSheet("font-weight: bold; color: #006d6d; font-size: 13px;")
        datetime_layout.addRow(start_label)
        
        # Start Datum und Zeit Layout
        start_layout = QHBoxLayout()
        start_layout.setContentsMargins(0, 0, 0, 0)
        start_layout.setSpacing(10)
        
        # Start Datum
        self.date_start = QDateEdit()
        self.date_start.setDisplayFormat(date_display_format)
        self.date_start.setCalendarPopup(True)
        self.date_start.setDate(QDate.currentDate())
        self.date_start.setMinimumWidth(120)
        self.date_start.setFixedHeight(25)
        self.date_start.setStyleSheet("""
            QDateEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                padding: 0px;
                font-size: 12px;
            }
            QDateEdit:focus {
                border: 2px solid #006d6d;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #606060;
                background-color: #555555;
            }
            QDateEdit::down-arrow {
                image: none;
                border: 2px solid #888888;
                width: 6px;
                height: 6px;
                border-top-color: transparent;
                border-left-color: transparent;
                border-right-color: #888888;
                border-bottom-color: #888888;
            }
        """)
        
        # Start Zeit
        self.time_start = QTimeEdit()
        self.time_start.setDisplayFormat("hh:mm")
        # Default: Nächste volle Stunde
        now = datetime.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        self.time_start.setTime(QTime(next_hour.hour, next_hour.minute))
        self.time_start.setMinimumWidth(100)
        self.time_start.setFixedHeight(25)
        self.time_start.setStyleSheet("""
            QTimeEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                padding: 0px;
                font-size: 12px;
            }
            QTimeEdit:focus {
                border: 2px solid #006d6d;
            }
        """)
        
        start_layout.addWidget(QLabel(self.tr("Date:")))
        start_layout.addWidget(self.date_start)
        start_layout.addWidget(QLabel(self.tr("Time:")))
        start_layout.addWidget(self.time_start)
        start_layout.addStretch()
        
        datetime_layout.addRow("", start_layout)

        # === END SECTION ===
        end_label = QLabel(self.tr("End:"))
        end_label.setStyleSheet("font-weight: bold; color: #006d6d; font-size: 13px;")
        datetime_layout.addRow(end_label)
        
        # End Datum und Zeit Layout
        end_layout = QHBoxLayout()
        end_layout.setContentsMargins(0, 0, 0, 0)
        end_layout.setSpacing(10)
        
        # End Datum
        self.date_end = QDateEdit()
        self.date_end.setDisplayFormat(date_display_format)  # Konsistentes Format wie Start-Datum
        self.date_end.setCalendarPopup(True)
        self.date_end.setDate(QDate.currentDate())
        self.date_end.setMinimumWidth(120)
        self.date_end.setFixedHeight(25)
        self.date_end.setStyleSheet("""
            QDateEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                padding: 0px;
                font-size: 12px;
            }
            QDateEdit:focus {
                border: 2px solid #006d6d;
            }
            QDateEdit::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 20px;
                border-left: 1px solid #606060;
                background-color: #555555;
            }
            QDateEdit::down-arrow {
                image: none;
                border: 2px solid #888888;
                width: 6px;
                height: 6px;
                border-top-color: transparent;
                border-left-color: transparent;
                border-right-color: #888888;
                border-bottom-color: #888888;
            }
        """)
        
        # End Zeit
        self.time_end = QTimeEdit()
        self.time_end.setDisplayFormat("hh:mm")
        # Default: Start + 1 Stunde
        end_time = next_hour + timedelta(hours=1)
        self.time_end.setTime(QTime(end_time.hour, end_time.minute))
        self.time_end.setMinimumWidth(100)
        self.time_end.setFixedHeight(25)
        self.time_end.setStyleSheet("""
            QTimeEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                padding: 0px;
                font-size: 12px;
            }
            QTimeEdit:focus {
                border: 2px solid #006d6d;
            }
        """)
        
        end_layout.addWidget(QLabel(self.tr("Date:")))
        end_layout.addWidget(self.date_end)
        end_layout.addWidget(QLabel(self.tr("Time:")))
        end_layout.addWidget(self.time_end)
        end_layout.addStretch()
        
        datetime_layout.addRow("", end_layout)

        self.layout.addWidget(datetime_group)
        
        # Initial: End-Minimum setzen
        self._update_end_minimums()

    def _setup_assignments_area(self):
        """Erstellt den Zuordnungs-Bereich."""
        assignments_group = QGroupBox(self.tr("Assignments"))
        assignments_layout = QFormLayout(assignments_group)
        assignments_layout.setContentsMargins(15, 20, 15, 15)
        assignments_layout.setSpacing(10)

        # Teams
        self.combo_teams = QComboBoxToFindData()
        self.combo_teams.setPlaceholderText(self.tr("Select teams..."))
        # TODO: Multi-select für Teams implementieren
        assignments_layout.addRow(self.tr("Teams:"), self.combo_teams)

        # Kategorien
        categories_layout = QHBoxLayout()
        categories_layout.setContentsMargins(0, 0, 0, 0)
        categories_layout.setSpacing(5)
        
        self.combo_categories = QComboBoxToFindData()
        self.combo_categories.setPlaceholderText(self.tr("Select category..."))
        
        self.btn_manage_categories = QPushButton(self.tr("Manage..."))
        self.btn_manage_categories.setMaximumWidth(80)
        self.btn_manage_categories.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        
        categories_layout.addWidget(self.combo_categories)
        categories_layout.addWidget(self.btn_manage_categories)
        
        assignments_layout.addRow(self.tr("Category:"), categories_layout)

        # Teilnehmer (Placeholder für zukünftige Implementierung)
        participants_layout = QHBoxLayout()
        participants_layout.setContentsMargins(0, 0, 0, 0)
        participants_layout.setSpacing(5)
        
        self.le_participants = QLineEdit()
        self.le_participants.setPlaceholderText(self.tr("No participants selected"))
        self.le_participants.setReadOnly(True)
        
        self.btn_select_participants = QPushButton(self.tr("Select..."))
        self.btn_select_participants.setMaximumWidth(80)
        self.btn_select_participants.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        
        participants_layout.addWidget(self.le_participants)
        participants_layout.addWidget(self.btn_select_participants)
        
        assignments_layout.addRow(self.tr("Participants:"), participants_layout)

        self.layout.addWidget(assignments_group)

    def _setup_options_area(self):
        """Erstellt den Options-Bereich (nur im Edit-Modus)."""
        options_group = QGroupBox(self.tr("Options"))
        options_layout = QVBoxLayout(options_group)
        options_layout.setContentsMargins(15, 15, 15, 15)
        options_layout.setSpacing(10)

        # Save as new Event Checkbox
        self.chk_save_as_new = QCheckBox(self.tr("Save as new event (duplicate)"))
        self.chk_save_as_new.setStyleSheet("color: white;")
        options_layout.addWidget(self.chk_save_as_new)

        self.layout.addWidget(options_group)

    def _setup_button_area(self):
        """Erstellt den Button-Bereich."""
        # Haupt-Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        
        # OK-Button Text anpassen
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_text = self.tr("Create Event") if self.is_new_mode else self.tr("Update Event")
        ok_button.setText(ok_text)

        # Delete-Button hinzufügen (nur im Edit-Modus)
        if self.is_edit_mode:
            self.btn_delete = QPushButton(self.tr("🗑️ Delete Event"))
            self.btn_delete.setStyleSheet("""
                QPushButton {
                    background-color: #804040;
                    color: white;
                    border: 1px solid #a05050;
                    border-radius: 3px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #905050;
                }
            """)
            self.button_box.addButton(self.btn_delete, QDialogButtonBox.ButtonRole.DestructiveRole)

        # Button-Styling
        self.button_box.setStyleSheet("""
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                padding: 8px 16px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:default {
                background-color: #006d6d;
                border: 1px solid #008d8d;
            }
            QPushButton:default:hover {
                background-color: #007d7d;
            }
        """)

        self.layout.addWidget(self.button_box)

    def _setup_data(self):
        """Lädt die notwendigen Daten (Teams, Kategorien)."""
        try:
            # Teams laden
            self.teams_cache = db_services.Team.get_all_from__project(self.project_id)

            # Persons laden
            self.persons_cache = db_services.Person.get_all_from__project(self.project_id)
            
            # Team-Dropdown befüllen
            self.combo_teams.addItem(self.tr("All teams"), "all_teams")
            for team in self.teams_cache:
                self.combo_teams.addItem(team.name, team.id)
            self.combo_teams.addItem("No teams", "no_teams")

            # Kategorien laden
            self.categories_cache = sorted(self.db_service.get_all_categories_by_project(self.project_id),
                                           key=lambda c: c.name)
            
            # Kategorie-Dropdown befüllen
            self.combo_categories.addItem(self.tr("No category"), None)
            for category in self.categories_cache:
                self.combo_categories.addItem(category.name, category.id)

        except Exception as e:
            logger.error(f"Error loading data: {e}")
            QMessageBox.warning(self, self.tr("Warning"), 
                              self.tr(f"Could not load all data: {str(e)}"))

    def _setup_connections(self):
        """Verbindet alle Signals und Slots."""
        # Dialog-Buttons
        self.button_box.accepted.connect(self._save_event)
        self.button_box.rejected.connect(self.reject)
        
        if self.is_edit_mode:
            self.btn_delete.clicked.connect(self._delete_event)

        # DateTime-Validierung und Auto-Updates
        self.date_start.dateChanged.connect(self._on_start_datetime_changed)
        self.time_start.timeChanged.connect(self._on_start_datetime_changed)

        # Placeholder-Connections für zukünftige Features
        self.btn_manage_categories.clicked.connect(self._manage_categories)
        self.btn_select_participants.clicked.connect(self._select_participants)

        # Save-as-new Checkbox
        if self.is_edit_mode:
            self.chk_save_as_new.toggled.connect(self._on_save_as_new_toggled)

    def _setup_defaults(self):
        """Setzt Default-Werte für neues Event."""
        # Default-Zeit: Nächste volle Stunde
        now = datetime.now()
        next_hour = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        self.date_start.setDate(QDate(next_hour.date()))
        self.time_start.setTime(QTime(next_hour.hour, next_hour.minute))
        
        # End automatisch setzen (wird durch Signal ausgelöst)
        self._on_start_datetime_changed()

    def _load_event(self):
        """Lädt das Event im Edit-Modus."""
        try:
            result = self.db_service.get_event(self.event_id)
            
            if isinstance(result, ErrorResponseSchema):
                QMessageBox.critical(self, self.tr("Error"), 
                                   self.tr(f"Could not load event: {result.message}"))
                self.reject()
                return
                
            self.current_event = result
            
            # Form-Felder befüllen
            self.le_title.setText(result.title)
            self.te_description.setPlainText(result.description)
            
            # DateTime-Felder
            self.date_start.setDate(QDate(result.start.date()))
            self.time_start.setTime(QTime(result.start.hour, result.start.minute))
            self.date_end.setDate(QDate(result.end.date()))
            self.time_end.setTime(QTime(result.end.hour, result.end.minute))
            
            # End-Minimums aktualisieren
            self._update_end_minimums()
            
            # Teams (erste Team auswählen wenn vorhanden)
            if len(result.teams) == 1:
                team = result.teams[0]
                self.combo_teams.setCurrentIndex(self.combo_teams.findData(team.id))
            elif len(result.teams) == len(self.teams_cache):  # Vereinfachung für jetzt
                self.combo_teams.setCurrentIndex(self.combo_teams.findData("all_teams"))
            else:
                self.combo_teams.setCurrentIndex(self.combo_teams.findData("no_teams"))
            
            # Kategorien (erste Kategorie auswählen wenn vorhanden)
            if result.categories:
                category = result.categories[0]  # Vereinfachung für jetzt
                self.combo_categories.setCurrentIndex(self.combo_categories.findData(category.id))
            
            # Teilnehmer-Anzeige und Cache
            self._current_participants = result.participants.copy()
            if result.participants:
                participants_text = f"{len(result.participants)} participants selected"
                self.le_participants.setText(participants_text)
                self.le_participants.setToolTip(", ".join([p.full_name for p in result.participants]))

            logger.info(f"Event loaded successfully: {result.title}")
            
        except Exception as e:
            logger.error(f"Error loading event: {e}")
            QMessageBox.critical(self, self.tr("Error"), 
                               self.tr(f"Unexpected error loading event: {str(e)}"))
            self.reject()

    def _on_start_datetime_changed(self):
        """Reagiert auf Änderungen der Start-DateTime und aktualisiert automatisch End-DateTime."""
        # End-Zeit automatisch auf Start + 1 Stunde setzen
        start_date = self.date_start.date().toPython()
        start_time = self.time_start.time().toPython()
        start_datetime = datetime.combine(start_date, start_time)
        
        # End: Start + 1 Stunde
        end_datetime = start_datetime + timedelta(hours=1)
        
        # End-Felder aktualisieren (ohne Signals auszulösen)
        self.date_end.blockSignals(True)
        self.time_end.blockSignals(True)
        
        self.date_end.setDate(QDate(end_datetime.date()))
        self.time_end.setTime(QTime(end_datetime.hour, end_datetime.minute))
        
        self.date_end.blockSignals(False)
        self.time_end.blockSignals(False)
        
        # End-Minimums aktualisieren
        self._update_end_minimums()

    def _update_end_minimums(self):
        """Aktualisiert die Minimum-Werte für End-Datum und -Zeit basierend auf Start."""
        start_date = self.date_start.date()
        start_time = self.time_start.time()
        
        # End-Datum kann nicht vor Start-Datum sein
        self.date_end.setMinimumDate(start_date)
        
        # Wenn End-Datum == Start-Datum, dann End-Zeit > Start-Zeit
        current_end_date = self.date_end.date()
        if current_end_date == start_date:
            # End-Zeit muss mindestens Start-Zeit + 1 Minute sein
            min_end_time = start_time.addSecs(60)  # 1 Minute später
            self.time_end.setMinimumTime(min_end_time)
        else:
            # Verschiedene Tage: End-Zeit hat keine Beschränkung
            self.time_end.setMinimumTime(QTime(0, 0))

    def _save_event(self):
        """Speichert das Event."""
        # Validation
        if not self._validate_form():
            return
        
        try:
            # Daten sammeln
            title = self.le_title.text().strip()
            description = self.te_description.toPlainText().strip()
            
            # DateTime aus getrennten Feldern zusammensetzen
            start_date = self.date_start.date().toPython()
            start_time = self.time_start.time().toPython()
            end_date = self.date_end.date().toPython()
            end_time = self.time_end.time().toPython()
            
            start_dt = datetime.combine(start_date, start_time)
            end_dt = datetime.combine(end_date, end_time)
            
            # Teams und Kategorien
            if self.combo_teams.currentData() == "all_teams":
                selected_team_ids = [t.id for t in self.teams_cache]
            elif self.combo_teams.currentData() == "no_teams":
                selected_team_ids = []
            else:
                selected_team_ids = [self.combo_teams.currentData()]
            
            selected_categories = []
            if self.combo_categories.currentData():
                category = self.combo_categories.currentData()
                selected_categories = [category]
            
            if self.is_new_mode or (self.is_edit_mode and self.chk_save_as_new.isChecked()):
                # Neues Event erstellen
                new_event = employee_event_schemas.EventCreate(
                    title=title,
                    description=description,
                    start=start_dt,
                    end=end_dt,
                    project_id=self.project_id,
                    category_ids=[category.id for category in selected_categories],
                    team_ids=selected_team_ids,
                    participant_ids=[participant.id for participant in self._current_participants]
                )
                command = event_commands.Create(new_event)
                self.controller.execute(command)
                
                if isinstance(command.result, ErrorResponseSchema):
                    QMessageBox.critical(self, self.tr("Error"), 
                                       self.tr(f"Could not create event: {command.result.message}"))
                    return
                
                QMessageBox.information(self, self.tr("Success"), 
                                      self.tr(f"Event '{title}' was created successfully."))
                
            else:
                # Update-Daten zusammenstellen
                update_data = employee_event_schemas.EventUpdate(
                    id=self.event_id,
                    title=title,
                    description=description,
                    start=start_dt,
                    end=end_dt,
                    category_ids=[category.id for category in selected_categories],
                    team_ids=selected_team_ids,
                    participant_ids=[participant.id for participant in self._current_participants]
                )
                # Bestehendes Event aktualisieren
                command = event_commands.Update(update_data)
                self.controller.execute(command)
                
                if isinstance(command.result, ErrorResponseSchema):
                    QMessageBox.critical(self, self.tr("Error"), 
                                       self.tr(f"Could not update event: {command.result.message}"))
                    return
                
                QMessageBox.information(self, self.tr("Success"), 
                                      self.tr(f"Event '{title}' was updated successfully."))
            
            self.accept()
            
        except Exception as e:
            logger.error(f"Error saving event: {e}")
            QMessageBox.critical(self, self.tr("Error"), 
                               self.tr(f"Unexpected error: {str(e)}"))

    def _delete_event(self):
        """Löscht das Event."""
        if not self.current_event:
            return
        
        # Bestätigung
        reply = QMessageBox.question(
            self, self.tr("Delete Event"),
            self.tr(f"Are you sure you want to delete the event '{self.current_event.title}'?\n\n"
                    f"Date: {date_to_string(self.current_event.start.date())}\n"
                    f"Time: {time_to_string(self.current_event.start.time())} - "
                    f"{time_to_string(self.current_event.end.time())}\n\n"
                    f"This action cannot be undone."),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                result = self.db_service.delete_event(self.event_id)
                
                if isinstance(result, ErrorResponseSchema):
                    QMessageBox.critical(self, self.tr("Error"), 
                                       self.tr(f"Could not delete event: {result.message}"))
                    return
                
                QMessageBox.information(self, self.tr("Success"), 
                                      self.tr(f"Event '{self.current_event.title}' was deleted successfully."))
                
                self.accept()
                
            except Exception as e:
                logger.error(f"Error deleting event: {e}")
                QMessageBox.critical(self, self.tr("Error"), 
                                   self.tr(f"Unexpected error: {str(e)}"))

    def _validate_form(self):
        """Validiert das Form."""
        # Titel erforderlich
        if not self.le_title.text().strip():
            QMessageBox.warning(self, self.tr("Validation Error"), 
                              self.tr("Please enter an event title."))
            self.le_title.setFocus()
            return False
        
        # Beschreibung erforderlich
        if not self.te_description.toPlainText().strip():
            QMessageBox.warning(self, self.tr("Validation Error"), 
                              self.tr("Please enter an event description."))
            self.te_description.setFocus()
            return False
        
        return True

    def _on_save_as_new_toggled(self, checked: bool):
        """Reagiert auf Save-as-New Checkbox."""
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_text = self.tr("Create New Event") if checked else self.tr("Update Event")
        ok_button.setText(ok_text)

    # Kategorie-Management
    def _manage_categories(self):
        """Öffnet Kategorie-Management-Dialog."""
        from gui.employee_event.dlg_employee_event_categories import DlgEmployeeEventCategories
        
        # Aktuell ausgewählte Kategorie ermitteln
        current_category = self.combo_categories.currentData()
        
        # Kategorie-Dialog öffnen
        dlg = DlgEmployeeEventCategories(self, self.project_id, current_category)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Kategorien-Liste aktualisieren
            self._refresh_categories_list()
            self.controller.add_to_undo_stack(dlg.controller.get_undo_stack())
            
            # Ausgewählte Kategorie setzen
            selected_category = dlg.get_selected_category()
            if selected_category:
                self._set_selected_category(selected_category.id)

    def _refresh_categories_list(self):
        """Aktualisiert die Kategorien-Liste nach Änderungen."""
        try:
            # Aktuelle Auswahl merken
            current_selection = self.combo_categories.currentData()
            
            # Kategorien neu laden
            categories = self.db_service.get_all_categories_by_project(self.project_id)
            
            self.categories_cache = sorted(categories, key=lambda c: c.name)
            
            # Combo-Box neu befüllen
            self.combo_categories.clear()
            self.combo_categories.addItem(self.tr("No category"), None)
            for category in self.categories_cache:
                self.combo_categories.addItem(category.name, category.id)
            
            # Vorherige Auswahl wiederherstellen wenn möglich
            if current_selection and current_selection in self.categories_cache:
                self._set_selected_category(current_selection)
                
        except Exception as e:
            logger.error(f"Error refreshing categories: {e}")

    def _set_selected_category(self, category_id: UUID):
        """Setzt die ausgewählte Kategorie im Dropdown."""
        if self.combo_categories.findData(category_id) >= 0:
            self.combo_categories.setCurrentIndex(self.combo_categories.findData(category_id))
        else:
            self.combo_categories.setCurrentIndex(0)

    def _select_participants(self):
        """Öffnet Teilnehmer-Auswahl-Dialog."""
        from gui.employee_event.dlg_participant_selection import DlgParticipantSelection
        
        # Aktuell ausgewählte Teilnehmer ermitteln
        current_participants = []
        
        # Im Edit-Modus: Teilnehmer aus dem geladenen Event extrahieren
        if self.is_edit_mode and self.current_event and self.current_event.participants:
            current_participants = self.current_event.participants.copy()
        
        # Zusätzlich: Falls Teilnehmer im UI-Feld angezeigt werden, diese auch berücksichtigen
        elif hasattr(self, '_current_participants') and self._current_participants:
            current_participants: list[schemas.Person] = self._current_participants.copy()
        
        # Teilnehmer-Dialog öffnen
        dlg = DlgParticipantSelection(self, self.project_id, self.date_start.date().toPython(), current_participants)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            # Ausgewählte Teilnehmer übernehmen
            selected_participants = dlg.get_selected_participants()
            self._current_participants = [p for p in self.persons_cache if p.id in selected_participants]  # Cache für spätere Aufrufe
            self._update_participants_display(self._current_participants)

    def _update_participants_display(self, participants: List[schemas.Person]):
        """Aktualisiert die Anzeige der ausgewählten Teilnehmer."""
        if participants:
            count_text = self.tr(f"{len(participants)} participants selected")
            self.le_participants.setText(count_text)
            self.le_participants.setToolTip(", ".join(p.full_name for p
                                                      in sorted(participants, key=lambda p: p.full_name)))
        else:
            self.le_participants.setText(self.tr("No participants selected"))
            self.le_participants.setToolTip("")
