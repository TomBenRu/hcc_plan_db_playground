"""
Dialog für Teilnehmer-Auswahl bei Employee Events.

Ermöglicht Multi-Select für Personen aus Teams mit Filter-Funktionalität
und intuitivem Drag & Drop Interface.
"""
import datetime
import logging
from typing import List, Optional, Set
from uuid import UUID

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem,
    QDialogButtonBox, QMessageBox, QPushButton, QGroupBox,
    QFormLayout, QSplitter
)

from database import db_services, schemas
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import setup_form_help

logger = logging.getLogger(__name__)


class DlgParticipantSelection(QDialog):
    """
    Dialog für Teilnehmer-Auswahl bei Employee Events.
    
    Features:
    - Multi-Select für Personen aus Teams
    - Team-Filter für bessere Übersicht
    - Freitextsuche in Namen
    - Drag & Drop Interface für intuitive Bedienung
    - Ausgewählte Teilnehmer-Übersicht
    """

    def __init__(self, parent: QWidget, project_id: UUID, start_date: datetime.date,
                 selected_participants: Optional[List[schemas.Person]] = None):
        """
        Initialisiert den Dialog.

        Args:
            parent: Übergeordnetes Widget
            project_id: ID des Projekts
            start_date: Startdatum des Events (datetime.date)
            selected_participants: Optional, vorausgewählte Teilnehmer als Liste von (full_name, person_id)
        """
        super().__init__(parent=parent)
        
        self.project_id = project_id
        self.start_date = start_date
        self.selected_participants = selected_participants or []
        
        # Daten-Cache
        self.persons_cache: List[schemas.PersonShow] = []
        self.teams_cache: List[schemas.Team] = []
        self.filtered_persons: List[schemas.PersonShow] = []
        
        # Return-Wert für aufrufenden Dialog
        self.selected_participants_result: set[UUID] = []
        
        self._setup_ui()
        self._setup_data()
        self._setup_connections()
        self._load_participants()
        
        # Vorausgewählte Teilnehmer setzen
        if self.selected_participants:
            self._set_selected_participants()
            
        # F1 Help Integration
        setup_form_help(self, "participant_selection")
            
        logger.info(f"Participant Selection Dialog initialized for project {project_id}")

    def _setup_ui(self):
        """Erstellt das komplette UI-Layout."""
        # Window-Konfiguration
        self.setWindowTitle(self.tr("Select Participants"))
        self.setMinimumSize(800, 600)
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
            QLineEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                padding: 5px;
            }
            QLineEdit:focus {
                border: 2px solid #006d6d;
            }
            QListWidget {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                selection-background-color: #006d6d;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #555555;
            }
            QListWidget::item:hover {
                background-color: #505050;
            }
            QListWidget::item:selected {
                background-color: #006d6d;
                color: white;
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

        # Filter-Bereich
        self._setup_filter_area()

        # Haupt-Bereich (Split: Verfügbare + Ausgewählte)
        self._setup_main_area()

        # Button-Bereich
        self._setup_button_area()

    def _setup_header(self):
        """Erstellt den Header-Bereich."""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Icon + Titel
        icon_label = QLabel("👥")
        icon_label.setStyleSheet("font-size: 24px;")
        
        title_label = QLabel(f"<b>{self.tr('Select Participants')}</b><br><small>{self.tr('Choose people for this event')}</small>")
        title_label.setStyleSheet("color: white; font-size: 14px;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.layout.addLayout(header_layout)

    def _setup_filter_area(self):
        """Erstellt den Filter-Bereich."""
        filter_group = QGroupBox(self.tr("Filters"))
        filter_layout = QFormLayout(filter_group)
        filter_layout.setContentsMargins(15, 20, 15, 15)
        filter_layout.setSpacing(10)

        # Team-Filter
        self.combo_team_filter = QComboBoxToFindData()
        self.combo_team_filter.setMinimumWidth(200)
        filter_layout.addRow(self.tr("Team:"), self.combo_team_filter)

        # Name-Suche
        search_layout = QHBoxLayout()
        search_layout.setSpacing(10)
        
        self.le_search = QLineEdit()
        self.le_search.setPlaceholderText(self.tr("Search by name..."))
        self.le_search.setMinimumWidth(200)
        
        self.btn_reset_filters = QPushButton(self.tr("Reset"))
        self.btn_reset_filters.setMaximumWidth(80)
        self.btn_reset_filters.setStyleSheet("""
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
        
        search_layout.addWidget(self.le_search)
        search_layout.addWidget(self.btn_reset_filters)
        
        filter_layout.addRow(self.tr("Search:"), search_layout)

        # Filter-Status
        self.lb_filter_status = QLabel()
        self.lb_filter_status.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")
        filter_layout.addRow("", self.lb_filter_status)

        self.layout.addWidget(filter_group)

    def _setup_main_area(self):
        """Erstellt den Haupt-Bereich mit verfügbaren und ausgewählten Teilnehmern."""
        # Splitter für resizable Bereiche
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #555555;
                width: 3px;
            }
        """)

        # Linke Seite: Verfügbare Personen
        self._setup_available_persons_area()

        # Mittlere Buttons
        self._setup_transfer_buttons()

        # Rechte Seite: Ausgewählte Teilnehmer
        self._setup_selected_participants_area()

        self.layout.addWidget(self.splitter)

    def _setup_available_persons_area(self):
        """Erstellt den Bereich für verfügbare Personen."""
        available_widget = QWidget()
        available_layout = QVBoxLayout(available_widget)
        available_layout.setContentsMargins(5, 5, 5, 5)
        available_layout.setSpacing(10)

        # Header
        available_header = QLabel(self.tr("Available People"))
        available_header.setStyleSheet("font-weight: bold; color: #006d6d; font-size: 13px; padding: 5px;")
        available_layout.addWidget(available_header)

        # Liste verfügbarer Personen
        self.list_available = QListWidget()
        self.list_available.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_available.setDragDropMode(QListWidget.DragDropMode.DragOnly)
        self.list_available.setSortingEnabled(True)
        self.list_available.sortItems(Qt.SortOrder.AscendingOrder)
        self.list_available.setMinimumHeight(300)
        available_layout.addWidget(self.list_available)

        # Info-Label
        self.lb_available_count = QLabel()
        self.lb_available_count.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")
        available_layout.addWidget(self.lb_available_count)

        self.splitter.addWidget(available_widget)

    def _setup_transfer_buttons(self):
        """Erstellt die Transfer-Buttons in der Mitte."""
        buttons_widget = QWidget()
        buttons_layout = QVBoxLayout(buttons_widget)
        buttons_layout.setContentsMargins(10, 50, 10, 50)
        buttons_layout.setSpacing(15)

        # Add Button
        self.btn_add = QPushButton("➤")
        self.btn_add.setToolTip(self.tr("Add selected people"))
        self.btn_add.setFixedSize(40, 40)
        
        # Add All Button
        self.btn_add_all = QPushButton("⏩")
        self.btn_add_all.setToolTip(self.tr("Add all people"))
        self.btn_add_all.setFixedSize(40, 40)
        
        # Remove Button
        self.btn_remove = QPushButton("◀")
        self.btn_remove.setToolTip(self.tr("Remove selected participants"))
        self.btn_remove.setFixedSize(40, 40)
        
        # Remove All Button
        self.btn_remove_all = QPushButton("⏪")
        self.btn_remove_all.setToolTip(self.tr("Remove all participants"))
        self.btn_remove_all.setFixedSize(40, 40)

        # Button-Styling
        button_style = """
            QPushButton {
                background-color: #555555;
                color: white;
                border: 1px solid #666666;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:pressed {
                background-color: #777777;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """
        
        for btn in [self.btn_add, self.btn_add_all, self.btn_remove, self.btn_remove_all]:
            btn.setStyleSheet(button_style)

        buttons_layout.addStretch()
        buttons_layout.addWidget(self.btn_add)
        buttons_layout.addWidget(self.btn_add_all)
        buttons_layout.addWidget(QLabel())  # Spacer
        buttons_layout.addWidget(self.btn_remove)
        buttons_layout.addWidget(self.btn_remove_all)
        buttons_layout.addStretch()

        buttons_widget.setMaximumWidth(60)
        self.splitter.addWidget(buttons_widget)

    def _setup_selected_participants_area(self):
        """Erstellt den Bereich für ausgewählte Teilnehmer."""
        selected_widget = QWidget()
        selected_layout = QVBoxLayout(selected_widget)
        selected_layout.setContentsMargins(5, 5, 5, 5)
        selected_layout.setSpacing(10)

        # Header
        selected_header = QLabel(self.tr("Selected Participants"))
        selected_header.setStyleSheet("font-weight: bold; color: #006d6d; font-size: 13px; padding: 5px;")
        selected_layout.addWidget(selected_header)

        # Liste ausgewählter Teilnehmer
        self.list_selected = QListWidget()
        self.list_selected.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.list_selected.setDragDropMode(QListWidget.DragDropMode.DropOnly)
        self.list_selected.setSortingEnabled(True)
        self.list_selected.sortItems(Qt.SortOrder.AscendingOrder)
        self.list_selected.setMinimumHeight(300)
        selected_layout.addWidget(self.list_selected)

        # Info-Label
        self.lb_selected_count = QLabel()
        self.lb_selected_count.setStyleSheet("color: #888888; font-style: italic; padding: 5px;")
        selected_layout.addWidget(self.lb_selected_count)

        self.splitter.addWidget(selected_widget)

        # Splitter-Verhältnis setzen (40% - 20% - 40%)
        self.splitter.setSizes([320, 60, 320])

    def _setup_button_area(self):
        """Erstellt den Button-Bereich."""
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        
        # OK-Button Text anpassen
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText(self.tr("Select Participants"))

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
        """Lädt die notwendigen Daten (Teams, Personen)."""
        try:
            # Teams laden
            self.teams_cache = db_services.Team.get_all_from__project(self.project_id)
            
            # Team-Filter befüllen
            self.combo_team_filter.addItem(self.tr("All Teams"), None)
            for team in sorted(self.teams_cache, key=lambda t: t.name):
                self.combo_team_filter.addItem(team.name, team.id)

            logger.info(f"Loaded {len(self.teams_cache)} teams")
            
        except Exception as e:
            logger.error(f"Error loading teams: {e}")
            QMessageBox.warning(self, self.tr("Warning"), 
                              self.tr("Could not load teams: {error}").format(error=str(e)))

    def _setup_connections(self):
        """Verbindet alle Signals und Slots."""
        # Dialog-Buttons
        self.button_box.accepted.connect(self._select_and_close)
        self.button_box.rejected.connect(self.reject)

        # Filter
        self.combo_team_filter.currentIndexChanged.connect(self._apply_filters)
        self.le_search.textChanged.connect(self._on_search_changed)
        self.btn_reset_filters.clicked.connect(self._reset_filters)

        # Transfer-Buttons
        self.btn_add.clicked.connect(self._add_selected)
        self.btn_add_all.clicked.connect(self._add_all)
        self.btn_remove.clicked.connect(self._remove_selected)
        self.btn_remove_all.clicked.connect(self._remove_all)

        # Listen-Events
        self.list_available.itemSelectionChanged.connect(self._update_button_states)
        self.list_selected.itemSelectionChanged.connect(self._update_button_states)
        self.list_available.itemDoubleClicked.connect(self._add_selected)
        self.list_selected.itemDoubleClicked.connect(self._remove_selected)

    def _load_participants(self):
        """Lädt alle verfügbaren Personen."""
        try:
            # Personen aus der Datenbank laden
            self.persons_cache = db_services.Person.get_all_from__project(self.project_id)
            
            # Filter anwenden
            self._apply_filters()
            
            logger.info(f"Loaded {len(self.persons_cache)} persons")
            
        except Exception as e:
            logger.error(f"Error loading persons: {e}")
            QMessageBox.warning(self, self.tr("Warning"), 
                              self.tr("Could not load persons: {error}").format(error=str(e)))

    def _apply_filters(self):
        """Wendet alle aktiven Filter an."""
        filtered = self.persons_cache.copy()
        filter_info = []

        # Team-Filter
        team_id = self.combo_team_filter.currentData()
        if team_id:
            team_name = self.combo_team_filter.currentText()
            filtered = [p for p in filtered if team_id in
                        [taa.team.id for taa in p.team_actor_assigns if not taa.end or taa.end > datetime.date.today()]]
            filter_info.append(self.tr("Team: {team_name}").format(team_name=team_name))

        # Name-Filter
        search_text = self.le_search.text().strip().lower()
        if search_text:
            filtered = [p for p in filtered
                        if (search_text in p.f_name.lower() or
                            search_text in p.l_name.lower() or
                            search_text in f"{p.full_name}".lower())]
            filter_info.append(self.tr("Search: '{search_text}'").format(search_text=search_text))

        self.filtered_persons = filtered

        # Filter-Status anzeigen
        if filter_info:
            self.lb_filter_status.setText(
                self.tr("Active filters: {filters} | {count} people").format(
                    filters=', '.join(filter_info),
                    count=len(filtered)
                )
            )
        else:
            self.lb_filter_status.setText(
                self.tr("No filters | {count} people").format(count=len(filtered))
            )

        # Listen aktualisieren
        self._update_available_list()
        self._update_counts()

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
        self.le_search.clear()
        self._apply_filters()

    def _update_available_list(self):
        """Aktualisiert die Liste verfügbarer Personen."""
        self.list_available.clear()
        
        for person in self.filtered_persons:
            if person.id not in [self.list_selected.item(i).data(Qt.ItemDataRole.UserRole)
                                 for i in range(self.list_selected.count())]:
                item = QListWidgetItem(person.full_name)
                item.setData(Qt.ItemDataRole.UserRole, person.id)
                item.setToolTip(self.tr("{name}\nEmail: {email}").format(name=person.full_name, email=person.email))
                self.list_available.addItem(item)

    def _update_counts(self):
        """Aktualisiert die Count-Labels."""
        available_count = self.list_available.count()
        selected_count = self.list_selected.count()
        
        self.lb_available_count.setText(self.tr("{count} people available").format(count=available_count))
        self.lb_selected_count.setText(self.tr("{count} participants selected").format(count=selected_count))

    def _update_button_states(self):
        """Aktualisiert den aktiviert/deaktiviert-Status der Transfer-Buttons."""
        has_available_selection = bool(self.list_available.selectedItems())
        has_selected_selection = bool(self.list_selected.selectedItems())
        has_available_items = self.list_available.count() > 0
        has_selected_items = self.list_selected.count() > 0

        self.btn_add.setEnabled(has_available_selection)
        self.btn_add_all.setEnabled(has_available_items)
        self.btn_remove.setEnabled(has_selected_selection)
        self.btn_remove_all.setEnabled(has_selected_items)

    def _add_selected(self):
        """Fügt ausgewählte Personen zu den Teilnehmern hinzu."""
        selected_items = self.list_available.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            # Item zu ausgewählten Teilnehmern hinzufügen
            new_item = QListWidgetItem(item.text())
            new_item.setData(Qt.ItemDataRole.UserRole, item.data(Qt.ItemDataRole.UserRole))
            new_item.setToolTip(item.toolTip())
            self.list_selected.addItem(new_item)
            
            # Item aus verfügbaren Personen entfernen
            row = self.list_available.row(item)
            self.list_available.takeItem(row)
        
        self._update_counts()
        self._update_button_states()

    def _add_all(self):
        """Fügt alle verfügbaren Personen zu den Teilnehmern hinzu."""
        while self.list_available.count() > 0:
            item = self.list_available.item(0)
            new_item = QListWidgetItem(item.text())
            new_item.setData(Qt.ItemDataRole.UserRole, item.data(Qt.ItemDataRole.UserRole))
            new_item.setToolTip(item.toolTip())
            self.list_selected.addItem(new_item)
            self.list_available.takeItem(0)
        
        self._update_counts()
        self._update_button_states()

    def _remove_selected(self):
        """Entfernt ausgewählte Teilnehmer."""
        selected_items = self.list_selected.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            # Item aus Teilnehmern entfernen
            row = self.list_selected.row(item)
            self.list_selected.takeItem(row)
        
        # Verfügbare Liste neu aufbauen (könnte jetzt wieder Personen enthalten)
        self._update_available_list()
        self._update_counts()
        self._update_button_states()

    def _remove_all(self):
        """Entfernt alle Teilnehmer."""
        self.list_selected.clear()
        self._update_available_list()
        self._update_counts()
        self._update_button_states()

    def _set_selected_participants(self):
        """Setzt die vorausgewählten Teilnehmer."""
        # Bereits vorhandene Auswahl löschen
        self.list_selected.clear()
        
        # Teilnehmer zu ausgewählten hinzufügen
        for person in self.selected_participants:
            item = QListWidgetItem(person.full_name)
            item.setData(Qt.ItemDataRole.UserRole, person.id)
            item.setToolTip(self.tr("{name}\nEmail: {email}").format(name=person.full_name, email=person.email))
            self.list_selected.addItem(item)
        
        # Listen aktualisieren
        self._update_available_list()
        self._update_counts()
        self._update_button_states()

    def _select_and_close(self):
        """Sammelt die ausgewählten Teilnehmer und schließt den Dialog."""
        self.selected_participants_result = {
            self.list_selected.item(i).data(Qt.ItemDataRole.UserRole)
            for i in range(self.list_selected.count())
        }
        self.accept()

    def get_selected_participants(self) -> set[UUID]:
        """Gibt die ausgewählten Teilnehmer zurück."""
        return self.selected_participants_result
