"""
Hauptfenster für Employee Event Management.

Stellt zwei Darstellungsmodi bereit:
- Listenansicht (sortiert nach Datum)  
- Monatskalenderansicht

Mit Filter-System für Teams, Kategorien und Freitextsuche.
"""

import logging
from functools import partial
from typing import List, Optional
from uuid import UUID

from PySide6.QtCore import Qt, Signal, QTimer, QLocale
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QTableWidget, QTableWidgetItem, QHeaderView,
    QCalendarWidget, QPushButton, QLineEdit, QGroupBox,
    QAbstractItemView, QMessageBox,
    QStackedWidget, QDialog
)

from configuration.general_settings import general_settings_handler
from database import db_services, schemas
from employee_event import EmployeeEventService, EventDetailSchema, ErrorResponseSchema
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import date_to_string, time_to_string

logger = logging.getLogger(__name__)


class FrmEmployeeEventMain(QWidget):
    """
    Hauptfenster für Employee Event Management.
    
    Features:
    - Toggle zwischen Listen- und Kalenderansicht
    - Filter für Teams, Kategorien, Freitextsuche
    - CRUD-Operationen für Events
    - Config-abhängige Datums/Zeit-Formatierung
    """

    # Signals für externe Kommunikation
    event_selected = Signal(UUID)  # Event-ID ausgewählt
    event_modified = Signal(UUID)  # Event wurde geändert

    def __init__(self, parent: QWidget, project_id: UUID):
        super().__init__(parent=parent)

        self.project_id = project_id
        self.service = EmployeeEventService()
        self.current_view_mode = "list"  # "list" oder "calendar"

        # Daten-Cache
        self.events_cache: List[EventDetailSchema] = []
        self.filtered_events: List[EventDetailSchema] = []
        self.teams_cache: List[schemas.Team] = []
        self.categories_cache: List[str] = []

        self._setup_ui()
        self._setup_data()
        self._setup_connections()

        # Initial-Load
        self.refresh_events()

        logger.info(f"Employee Event Main Window initialized for project {project_id}")

    def _setup_ui(self):
        """Erstellt das komplette UI-Layout."""
        self.setObjectName("FrmEmployeeEventMain")
        self.setMinimumSize(800, 600)

        # Haupt-Layout
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(10)

        # Header-Bereich
        self._setup_header()

        # Filter-Bereich  
        self._setup_filter_area()

        # Ansichten-Bereich
        self._setup_view_area()

        # Aktions-Bereich
        self._setup_action_area()

    def _setup_header(self):
        """Erstellt den Header mit Titel und View-Toggle."""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Titel
        self.lb_title = QLabel(self.tr("Employee Events"))
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        self.lb_title.setFont(title_font)
        header_layout.addWidget(self.lb_title)

        # Spacer
        header_layout.addStretch()

        # View-Toggle-Buttons
        self.btn_view_list = QPushButton(self.tr("📋 List View"))
        self.btn_view_list.setCheckable(True)
        self.btn_view_list.setChecked(True)
        self.btn_view_list.setMinimumWidth(120)

        self.btn_view_calendar = QPushButton(self.tr("📅 Calendar View"))
        self.btn_view_calendar.setCheckable(True)
        self.btn_view_calendar.setMinimumWidth(120)

        # View-Toggle-Styling
        self._setup_view_toggle_styling()

        header_layout.addWidget(self.btn_view_list)
        header_layout.addWidget(self.btn_view_calendar)

        self.layout.addLayout(header_layout)

    def _setup_view_toggle_styling(self):
        """Styling für die View-Toggle-Buttons."""
        active_style = """
            QPushButton {
                background-color: #006d6d;
                color: white;
                border: 2px solid #004d4d;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
        """

        inactive_style = """
            QPushButton {
                background-color: #404040;
                color: #cccccc;
                border: 2px solid #606060;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #505050;
                color: white;
            }
        """

        self.btn_view_list.setStyleSheet(active_style)
        self.btn_view_calendar.setStyleSheet(inactive_style)

    def _setup_filter_area(self):
        """Erstellt den Filter-Bereich."""
        self.group_filter = QGroupBox(self.tr("Filters"))
        filter_layout = QGridLayout(self.group_filter)
        filter_layout.setContentsMargins(10, 15, 10, 10)
        filter_layout.setSpacing(10)

        # Team-Filter
        filter_layout.addWidget(QLabel(self.tr("Team:")), 0, 0)
        self.combo_team_filter = QComboBoxToFindData()
        self.combo_team_filter.setMinimumWidth(150)
        filter_layout.addWidget(self.combo_team_filter, 0, 1)

        # Kategorie-Filter  
        filter_layout.addWidget(QLabel(self.tr("Category:")), 0, 2)
        self.combo_category_filter = QComboBoxToFindData()
        self.combo_category_filter.setMinimumWidth(150)
        filter_layout.addWidget(self.combo_category_filter, 0, 3)

        # Freitext-Suche
        filter_layout.addWidget(QLabel(self.tr("Search:")), 1, 0)
        self.le_search = QLineEdit()
        self.le_search.setPlaceholderText(self.tr("Search in title and description..."))
        self.le_search.setMinimumWidth(200)
        filter_layout.addWidget(self.le_search, 1, 1, 1, 2)

        # Filter-Reset-Button
        self.btn_reset_filters = QPushButton(self.tr("Reset Filters"))
        self.btn_reset_filters.setMaximumWidth(120)
        filter_layout.addWidget(self.btn_reset_filters, 1, 3)

        # Filter-Status-Label
        self.lb_filter_status = QLabel()
        self.lb_filter_status.setStyleSheet("color: #888888; font-style: italic;")
        filter_layout.addWidget(self.lb_filter_status, 2, 0, 1, 4)

        self.layout.addWidget(self.group_filter)

    def _setup_view_area(self):
        """Erstellt den Haupt-Ansichts-Bereich."""
        # Stacked Widget für sauberes Umschalten zwischen Views
        self.view_stack = QStackedWidget(self)
        self.view_stack.setContentsMargins(0, 0, 0, 0)
        
        # Explizite Größenpolitik für das StackedWidget
        from PySide6.QtWidgets import QSizePolicy
        self.view_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Listen-Ansicht erstellen
        self._setup_list_view()
        
        # Kalender-Ansicht erstellen  
        self._setup_calendar_view()

        # Widgets zum Stack hinzufügen (WICHTIG: Reihenfolge beachten)
        self.list_view_index = self.view_stack.addWidget(self.table_events)
        self.calendar_view_index = self.view_stack.addWidget(self.calendar_widget)

        # Initial Liste anzeigen
        self.view_stack.setCurrentIndex(self.list_view_index)

        # Zum Haupt-Layout hinzufügen
        self.layout.addWidget(self.view_stack)

    def _setup_list_view(self):
        """Erstellt die Listen-Ansicht."""
        # WICHTIG: Kein Parent setzen - QStackedWidget übernimmt das
        self.table_events = QTableWidget()
        self.table_events.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table_events.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table_events.setAlternatingRowColors(True)

        # Spalten definieren: Datum | Zeitspanne | Name | Kategorie | Teams  
        columns = [
            self.tr("Date"),
            self.tr("Time"),
            self.tr("Title"),
            self.tr("Category"),
            self.tr("Teams"),
            self.tr("Participants")
        ]

        self.table_events.setColumnCount(len(columns))
        self.table_events.setHorizontalHeaderLabels(columns)

        # Header-Styling
        header = self.table_events.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)  # Title-Spalte dehnbar
        header.setStyleSheet("""
            QHeaderView::section {
                background-color: #006d6d;
                color: white;
                padding: 8px;
                border: 1px solid #004d4d;
                font-weight: bold;
            }
        """)

        # Tabellen-Styling
        self.table_events.setStyleSheet("""
            QTableWidget {
                background-color: #2d2d2d;
                color: white;
                gridline-color: #555555;
                selection-background-color: #006d6d;
                selection-color: white;
            }
            QTableWidget::item {
                padding: 5px;
                border: none;
            }
            QTableWidget::item:alternate {
                background-color: #353535;
            }
            QTableWidget::item:selected {
                background-color: #006d6d;
                color: white;
            }
        """)

    def _setup_calendar_view(self):
        """Erstellt die Kalender-Ansicht."""
        # WICHTIG: Kein Parent setzen - QStackedWidget übernimmt das
        self.calendar_widget = QWidget()
        
        # WICHTIG: Expliziter Hintergrund für das Calendar-Widget
        self.calendar_widget.setStyleSheet("""
            QWidget {
                background-color: #2d2d2d;
                color: white;
            }
        """)
        
        calendar_layout = QVBoxLayout(self.calendar_widget)
        calendar_layout.setContentsMargins(10, 10, 10, 10)
        calendar_layout.setSpacing(15)

        # QCalendarWidget für Basis-Funktionalität (nimmt den meisten Platz ein)
        self.calendar = QCalendarWidget(self.calendar_widget)

        # Kalender-Konfiguration basierend auf User-Settings
        date_format_settings = general_settings_handler.get_general_settings().date_format_settings
        locale = QLocale(
            QLocale.Language(date_format_settings.language),
            QLocale.Country(date_format_settings.country)
        )
        self.calendar.setLocale(locale)

        # Kalender-Styling
        self.calendar.setStyleSheet("""
            QCalendarWidget {
                background-color: #353535;
                color: white;
                border: 2px solid #006d6d;
                border-radius: 8px;
                font-size: 12px;
            }
            QCalendarWidget QAbstractItemView {
                background-color: #404040;
                color: white;
                selection-background-color: #006d6d;
            }
            QCalendarWidget QWidget {
                background-color: #353535;
                color: white;
            }
        """)

        # Kalender bekommt den Hauptanteil des Platzes
        calendar_layout.addWidget(self.calendar, 3)  # Stretch-Faktor 3

        # Kompakte Event-Details für das ausgewählte Datum
        events_section = QGroupBox(self.tr("Events on Selected Date"))
        events_section.setStyleSheet("""
            QGroupBox {
                background-color: #353535;
                border: 2px solid #555555;
                border-radius: 8px;
                margin: 5px;
                padding-top: 10px;
                font-weight: bold;
                color: #006d6d;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: #006d6d;
            }
        """)
        
        events_layout = QVBoxLayout(events_section)
        events_layout.setContentsMargins(10, 10, 10, 10)
        events_layout.setSpacing(5)

        # Datum-Label
        self.lb_calendar_date = QLabel(self.tr("Select a date to view events"))
        self.lb_calendar_date.setStyleSheet("""
            QLabel {
                font-weight: bold; 
                color: #006d6d; 
                background-color: transparent;
                padding: 5px;
                font-size: 13px;
            }
        """)
        events_layout.addWidget(self.lb_calendar_date)

        # KOMPAKTE Events-Tabelle für das ausgewählte Datum
        self.list_calendar_events = QTableWidget()
        self.list_calendar_events.setColumnCount(3)
        self.list_calendar_events.setHorizontalHeaderLabels([
            self.tr("Time"), self.tr("Title"), self.tr("Category")
        ])
        
        # Kompakte Tabelle - maximale Höhe begrenzen
        self.list_calendar_events.setMaximumHeight(150)  # WICHTIG: Begrenzte Höhe
        self.list_calendar_events.setAlternatingRowColors(True)
        self.list_calendar_events.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.list_calendar_events.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Header-Styling für kompakte Tabelle
        events_header = self.list_calendar_events.horizontalHeader()
        events_header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        events_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)  # Title dehnbar
        events_header.setMaximumHeight(25)  # Kompakter Header
        
        # Styling für Events-Tabelle - deutlich anders als Main-List
        self.list_calendar_events.setStyleSheet("""
            QTableWidget {
                background-color: #404040;
                color: white;
                gridline-color: #666666;
                selection-background-color: #006d6d;
                selection-color: white;
                border: 1px solid #666666;
                border-radius: 5px;
                font-size: 11px;
            }
            QTableWidget::item {
                padding: 3px;
                border: none;
            }
            QTableWidget::item:alternate {
                background-color: #383838;
            }
            QTableWidget::item:selected {
                background-color: #006d6d;
                color: white;
            }
            QHeaderView::section {
                background-color: #555555;
                color: white;
                padding: 4px;
                border: 1px solid #666666;
                font-weight: bold;
                font-size: 10px;
            }
        """)
        
        events_layout.addWidget(self.list_calendar_events)

        # Events-Sektion bekommt minimalen Platz
        calendar_layout.addWidget(events_section, 1)  # Stretch-Faktor 1

    def _setup_action_area(self):
        """Erstellt den Aktions-Bereich."""
        action_layout = QHBoxLayout()
        action_layout.setContentsMargins(0, 10, 0, 0)

        # Event-Management-Buttons
        self.btn_new_event = QPushButton(self.tr("➕ New Event"))
        self.btn_edit_event = QPushButton(self.tr("✏️ Edit Event"))
        self.btn_delete_event = QPushButton(self.tr("🗑️ Delete Event"))
        self.btn_categories = QPushButton(self.tr("📂 Manage Categories"))

        # Button-Styling
        button_style = """
            QPushButton {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 5px;
                padding: 8px 16px;
                font-weight: bold;
                min-width: 120px;
            }
            QPushButton:hover {
                background-color: #505050;
            }
            QPushButton:pressed {
                background-color: #606060;
            }
            QPushButton:disabled {
                background-color: #303030;
                color: #666666;
            }
        """

        for btn in [self.btn_new_event, self.btn_edit_event,
                    self.btn_delete_event, self.btn_categories]:
            btn.setStyleSheet(button_style)

        # Spezial-Styling für gefährliche Aktionen
        self.btn_delete_event.setStyleSheet(button_style.replace("#404040", "#804040"))

        action_layout.addWidget(self.btn_new_event)
        action_layout.addWidget(self.btn_edit_event)
        action_layout.addWidget(self.btn_delete_event)
        action_layout.addStretch()
        action_layout.addWidget(self.btn_categories)

        # Status-Bereich
        self.lb_status = QLabel()
        self.lb_status.setStyleSheet("color: #888888; font-style: italic;")
        action_layout.addWidget(self.lb_status)

        self.layout.addLayout(action_layout)

        # Initial: Edit/Delete deaktivieren
        self.btn_edit_event.setEnabled(False)
        self.btn_delete_event.setEnabled(False)

    def _setup_data(self):
        """Initialisiert die Daten-Caches."""
        # Teams laden
        try:
            self.teams_cache = db_services.Team.get_all_from_project(self.project_id)

            # Team-Filter befüllen
            self.combo_team_filter.addItem(self.tr("All Teams"), None)
            for team in self.teams_cache:
                self.combo_team_filter.addItem(team.name, team.id)

        except Exception as e:
            logger.error(f"Error loading teams: {e}")
            self.teams_cache = []

        # Kategorien werden beim ersten Event-Load gefüllt
        self.combo_category_filter.addItem(self.tr("All Categories"), None)

    def _setup_connections(self):
        """Verbindet alle Signals und Slots."""
        # View-Toggle
        self.btn_view_list.clicked.connect(partial(self._switch_view, "list"))
        self.btn_view_calendar.clicked.connect(partial(self._switch_view, "calendar"))

        # Filter
        self.combo_team_filter.currentIndexChanged.connect(self._apply_filters)
        self.combo_category_filter.currentIndexChanged.connect(self._apply_filters)
        self.le_search.textChanged.connect(self._on_search_changed)
        self.btn_reset_filters.clicked.connect(self._reset_filters)

        # Listen-Ansicht
        self.table_events.itemSelectionChanged.connect(self._on_event_selection_changed)
        self.table_events.itemDoubleClicked.connect(self._on_event_double_clicked)

        # Kalender-Ansicht
        self.calendar.selectionChanged.connect(self._on_calendar_date_changed)
        self.list_calendar_events.itemSelectionChanged.connect(self._on_calendar_event_selection_changed)
        self.list_calendar_events.itemDoubleClicked.connect(self._on_event_double_clicked)

        # Aktionen
        self.btn_new_event.clicked.connect(self._create_new_event)
        self.btn_edit_event.clicked.connect(self._edit_selected_event)
        self.btn_delete_event.clicked.connect(self._delete_selected_event)
        self.btn_categories.clicked.connect(self._manage_categories)

    def _switch_view(self, view_mode: str):
        """Wechselt zwischen Listen- und Kalenderansicht."""
        if view_mode == self.current_view_mode:
            return

        self.current_view_mode = view_mode

        if view_mode == "list":
            # Liste aktivieren 
            self.view_stack.setCurrentIndex(self.list_view_index)

            # Button-Styling anpassen
            self.btn_view_list.setChecked(True)
            self.btn_view_calendar.setChecked(False)
            self._update_view_button_styling()

            self._update_list_view()

        elif view_mode == "calendar":
            # Kalender aktivieren
            self.view_stack.setCurrentIndex(self.calendar_view_index)

            # Button-Styling anpassen
            self.btn_view_list.setChecked(False)
            self.btn_view_calendar.setChecked(True)
            self._update_view_button_styling()

            self._update_calendar_view()

        logger.info(f"Switched to {view_mode} view")

    def _update_view_button_styling(self):
        """Aktualisiert das Styling der View-Toggle-Buttons."""
        active_style = """
            QPushButton {
                background-color: #006d6d;
                color: white;
                border: 2px solid #004d4d;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
        """

        inactive_style = """
            QPushButton {
                background-color: #404040;
                color: #cccccc;
                border: 2px solid #606060;
                border-radius: 5px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #505050;
                color: white;
            }
        """

        if self.current_view_mode == "list":
            self.btn_view_list.setStyleSheet(active_style)
            self.btn_view_calendar.setStyleSheet(inactive_style)
        else:
            self.btn_view_list.setStyleSheet(inactive_style)
            self.btn_view_calendar.setStyleSheet(active_style)

    def refresh_events(self):
        """Lädt alle Events neu vom Service."""
        try:
            self.lb_status.setText(self.tr("Loading events..."))

            # Events vom Service laden
            event_list = self.service.get_all_events(self.project_id)
            self.events_cache = event_list.events

            # Kategorien-Cache aktualisieren
            categories = set()
            for event in self.events_cache:
                categories.update(event.categories)

            # Kategorie-Filter aktualisieren falls neue Kategorien
            current_categories = {self.combo_category_filter.itemText(i)
                                  for i in range(1, self.combo_category_filter.count())}
            new_categories = categories - current_categories

            for category in sorted(new_categories):
                self.combo_category_filter.addItem(category, category)

            # Filter anwenden und Views aktualisieren
            self._apply_filters()

            # Status aktualisieren
            count = len(self.events_cache)
            self.lb_status.setText(self.tr(f"Loaded {count} events"))

            logger.info(f"Refreshed {count} events")

        except Exception as e:
            logger.error(f"Error refreshing events: {e}")
            self.lb_status.setText(self.tr("Error loading events"))
            QMessageBox.critical(self, self.tr("Error"),
                                 self.tr(f"Could not load events: {str(e)}"))

    def _apply_filters(self):
        """Wendet alle aktiven Filter an."""
        filtered = self.events_cache.copy()
        filter_info = []

        # Team-Filter
        team_id = self.combo_team_filter.currentData()
        if team_id:
            team_name = self.combo_team_filter.currentText()
            filtered = [e for e in filtered if team_name in e.teams]
            filter_info.append(f"Team: {team_name}")

        # Kategorie-Filter
        category = self.combo_category_filter.currentData()
        if category:
            filtered = [e for e in filtered if category in e.categories]
            filter_info.append(f"Category: {category}")

        # Suchtext-Filter
        search_text = self.le_search.text().strip().lower()
        if search_text:
            filtered = [e for e in filtered
                        if (search_text in e.title.lower() or
                            search_text in e.description.lower())]
            filter_info.append(f"Search: '{search_text}'")

        self.filtered_events = filtered

        # Filter-Status anzeigen
        if filter_info:
            self.lb_filter_status.setText(
                self.tr(f"Active filters: {', '.join(filter_info)} | {len(filtered)} events")
            )
        else:
            self.lb_filter_status.setText(
                self.tr(f"No filters | {len(filtered)} events")
            )

        # Views aktualisieren
        if self.current_view_mode == "list":
            self._update_list_view()
        else:
            self._update_calendar_view()

    def _on_search_changed(self):
        """Reagiert auf Änderungen im Suchfeld mit Verzögerung."""
        # Timer für verzögerte Suche (bessere Performance)
        if hasattr(self, '_search_timer'):
            self._search_timer.stop()

        self._search_timer = QTimer()
        self._search_timer.setSingleShot(True)
        self._search_timer.timeout.connect(self._apply_filters)
        self._search_timer.start(300)  # 300ms Verzögerung

    def _reset_filters(self):
        """Setzt alle Filter zurück."""
        self.combo_team_filter.setCurrentIndex(0)
        self.combo_category_filter.setCurrentIndex(0)
        self.le_search.clear()
        self._apply_filters()

    def _update_list_view(self):
        """Aktualisiert die Listen-Ansicht mit gefilterten Events."""
        self.table_events.setRowCount(len(self.filtered_events))

        # Events nach Datum sortieren
        sorted_events = sorted(self.filtered_events, key=lambda e: e.start)

        for row, event in enumerate(sorted_events):
            # Datum (mit Config-Formatierung)
            date_item = QTableWidgetItem(date_to_string(event.start.date()))
            date_item.setData(Qt.ItemDataRole.UserRole, event.id)
            self.table_events.setItem(row, 0, date_item)

            # Zeitspanne (mit Config-Formatierung)
            start_time = time_to_string(event.start.time())
            end_time = time_to_string(event.end.time())
            time_item = QTableWidgetItem(f"{start_time} - {end_time}")
            self.table_events.setItem(row, 1, time_item)

            # Titel
            title_item = QTableWidgetItem(event.title)
            title_item.setToolTip(event.description)
            self.table_events.setItem(row, 2, title_item)

            # Kategorie
            categories = ", ".join(event.categories) if event.categories else self.tr("No category")
            category_item = QTableWidgetItem(categories)
            self.table_events.setItem(row, 3, category_item)

            # Teams
            teams = ", ".join(event.teams) if event.teams else self.tr("No teams")
            teams_item = QTableWidgetItem(teams)
            self.table_events.setItem(row, 4, teams_item)

            # Teilnehmer-Anzahl
            participants_item = QTableWidgetItem(str(event.participant_count))
            participants_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            if event.participants:
                participants_item.setToolTip(", ".join(event.participants))
            self.table_events.setItem(row, 5, participants_item)

    def _update_calendar_view(self):
        """Aktualisiert die Kalender-Ansicht."""
        # TODO: Implementierung der Kalender-Event-Anzeige
        # Für jetzt einfache Anzeige der Events am ausgewählten Datum
        self._on_calendar_date_changed()

    def _on_calendar_date_changed(self):
        """Reagiert auf Datums-Änderung im Kalender."""
        selected_date = self.calendar.selectedDate().toPython()

        # Events für das ausgewählte Datum finden
        events_on_date = [e for e in self.filtered_events
                          if e.start.date() == selected_date]

        # Header aktualisieren
        formatted_date = date_to_string(selected_date)
        count = len(events_on_date)
        self.lb_calendar_date.setText(
            self.tr(f"{formatted_date} - {count} events")
        )

        # Event-Liste aktualisieren
        self.list_calendar_events.setRowCount(count)

        for row, event in enumerate(sorted(events_on_date, key=lambda e: e.start.time())):
            # Zeit
            start_time = time_to_string(event.start.time())
            end_time = time_to_string(event.end.time())
            time_item = QTableWidgetItem(f"{start_time} - {end_time}")
            self.list_calendar_events.setItem(row, 0, time_item)

            # Titel
            title_item = QTableWidgetItem(event.title)
            title_item.setToolTip(event.description)
            title_item.setData(Qt.ItemDataRole.UserRole, event.id)
            self.list_calendar_events.setItem(row, 1, title_item)

            # Kategorie
            categories = ", ".join(event.categories) if event.categories else self.tr("No category")
            category_item = QTableWidgetItem(categories)
            self.list_calendar_events.setItem(row, 2, category_item)

    def _on_event_selection_changed(self):
        """Reagiert auf Auswahl-Änderung in der Listen-Ansicht."""
        has_selection = bool(self.table_events.currentRow() >= 0)

        self.btn_edit_event.setEnabled(has_selection)
        self.btn_delete_event.setEnabled(has_selection)

        if has_selection:
            # Event-ID aus der ersten Spalte holen
            current_row = self.table_events.currentRow()
            if current_row >= 0:
                event_id_item = self.table_events.item(current_row, 0)
                if event_id_item and event_id_item.data(Qt.ItemDataRole.UserRole):
                    event_id = event_id_item.data(Qt.ItemDataRole.UserRole)
                    self.event_selected.emit(event_id)

    def _on_calendar_event_selection_changed(self):
        """Reagiert auf Auswahl-Änderung in der Kalender-Events-Liste."""
        has_selection = bool(self.list_calendar_events.currentRow() >= 0)

        self.btn_edit_event.setEnabled(has_selection)
        self.btn_delete_event.setEnabled(has_selection)

        if has_selection:
            # Event-ID aus der Titel-Spalte holen
            current_row = self.list_calendar_events.currentRow()
            if current_row >= 0:
                title_item = self.list_calendar_events.item(current_row, 1)
                if title_item and title_item.data(Qt.ItemDataRole.UserRole):
                    event_id = title_item.data(Qt.ItemDataRole.UserRole)
                    self.event_selected.emit(event_id)

    def _on_event_double_clicked(self, item):
        """Reagiert auf Doppelklick in der Listen-Ansicht."""
        self._edit_selected_event()

    def get_selected_event_id(self) -> Optional[UUID]:
        """Gibt die ID des aktuell ausgewählten Events zurück."""
        if self.current_view_mode == "list":
            current_row = self.table_events.currentRow()
            if current_row >= 0:
                event_id_item = self.table_events.item(current_row, 0)
                if event_id_item:
                    return event_id_item.data(Qt.ItemDataRole.UserRole)

        elif self.current_view_mode == "calendar":
            current_row = self.list_calendar_events.currentRow()
            if current_row >= 0:
                title_item = self.list_calendar_events.item(current_row, 1)
                if title_item:
                    return title_item.data(Qt.ItemDataRole.UserRole)

        return None

    def get_selected_event(self) -> Optional[EventDetailSchema]:
        """Gibt das aktuell ausgewählte Event zurück."""
        event_id = self.get_selected_event_id()
        if event_id:
            return next((e for e in self.filtered_events if e.id == event_id), None)
        return None

    # Event-Aktionen mit Dialog-Integration

    def _create_new_event(self):
        """Öffnet Dialog für neues Event."""
        from gui.employee_event.dlg_employee_event_details import DlgEmployeeEventDetails
        
        dialog = DlgEmployeeEventDetails(self, self.project_id)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Events neu laden nach erfolgreichem Erstellen
            self.refresh_events()
            logger.info("New event created successfully")

    def _edit_selected_event(self):
        """Öffnet Dialog für Event-Bearbeitung."""
        event = self.get_selected_event()
        if not event:
            QMessageBox.warning(self, self.tr("No Selection"), 
                              self.tr("Please select an event to edit."))
            return
            
        from gui.employee_event.dlg_employee_event_details import DlgEmployeeEventDetails
        
        dialog = DlgEmployeeEventDetails(self, self.project_id, event.id)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Events neu laden nach erfolgreichem Update
            self.refresh_events()
            self.event_modified.emit(event.id)
            logger.info(f"Event {event.id} updated successfully")

    def _delete_selected_event(self):
        """Löscht das ausgewählte Event."""
        event = self.get_selected_event()
        if not event:
            return

        # Bestätigung
        reply = QMessageBox.question(
            self, self.tr("Delete Event"),
            self.tr(f"Are you sure you want to delete the event '{event.title}'?\n\n"
                    f"Date: {date_to_string(event.start.date())}\n"
                    f"Time: {time_to_string(event.start.time())} - {time_to_string(event.end.time())}"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            try:
                result = self.service.delete_event(event.id)

                if isinstance(result, ErrorResponseSchema):
                    QMessageBox.critical(self, self.tr("Error"),
                                         self.tr(f"Could not delete event: {result.message}"))
                else:
                    QMessageBox.information(self, self.tr("Success"),
                                            self.tr(f"Event '{event.title}' was deleted successfully."))

                    # Events neu laden
                    self.refresh_events()
                    self.event_modified.emit(event.id)

            except Exception as e:
                logger.error(f"Error deleting event {event.id}: {e}")
                QMessageBox.critical(self, self.tr("Error"),
                                     self.tr(f"Unexpected error: {str(e)}"))

    def _manage_categories(self):
        """Öffnet Dialog für Kategorie-Management."""
        # TODO: Implementierung mit dlg_employee_event_categories.py
        QMessageBox.information(self, self.tr("Manage Categories"),
                                self.tr("Category management dialog will be implemented next."))
