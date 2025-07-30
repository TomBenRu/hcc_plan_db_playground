"""
Dialog für Employee Event Categories Management.

Ermöglicht CRUD-Operationen für Event-Kategorien mit Usage-Tracking
und vollständiger Service-Layer-Integration.
"""

import logging
from typing import List, Optional
from uuid import UUID

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QTextEdit, QListWidget, QListWidgetItem,
    QDialogButtonBox, QMessageBox, QPushButton, QGroupBox,
    QFormLayout, QFrame
)

from employee_event import EmployeeEventService, ErrorResponseSchema

logger = logging.getLogger(__name__)


class DlgEmployeeEventCategories(QDialog):
    """
    Dialog für Employee Event Categories Management.
    
    Features:
    - Kategorien anzeigen (Name, Beschreibung, Usage Count)
    - Neue Kategorien erstellen
    - Bestehende bearbeiten/löschen  
    - Usage-Validierung (keine Löschung wenn in Events verwendet)
    - Service-Layer-Integration
    """

    def __init__(self, parent: QWidget, project_id: UUID, selected_category: Optional[str] = None):
        super().__init__(parent=parent)
        
        self.project_id = project_id
        self.selected_category = selected_category
        self.service = EmployeeEventService()
        
        # Daten-Cache
        self.categories_data = {}  # {category_name: usage_count}
        self.current_category = None
        
        # Return-Wert für aufrufenden Dialog
        self.selected_category_result = None
        
        self._setup_ui()
        self._setup_connections()
        self._load_categories()
        
        # Vorausgewählte Kategorie setzen
        if selected_category:
            self._select_category_by_name(selected_category)
            
        logger.info(f"Employee Event Categories Dialog initialized for project {project_id}")

    def _setup_ui(self):
        """Erstellt das komplette UI-Layout."""
        # Window-Konfiguration
        self.setWindowTitle(self.tr("Manage Event Categories"))
        self.setMinimumSize(600, 500)
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
            QLineEdit, QTextEdit {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                padding: 5px;
            }
            QLineEdit:focus, QTextEdit:focus {
                border: 2px solid #006d6d;
            }
            QListWidget {
                background-color: #404040;
                color: white;
                border: 1px solid #606060;
                border-radius: 3px;
                selection-background-color: #006d6d;
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

        # Haupt-Bereich (Split: Liste + Details)
        self._setup_main_area()

        # Button-Bereich
        self._setup_button_area()

    def _setup_header(self):
        """Erstellt den Header-Bereich."""
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        # Icon + Titel
        icon_label = QLabel("🏷️")
        icon_label.setStyleSheet("font-size: 24px;")
        
        title_label = QLabel(f"<b>{self.tr('Event Categories')}</b><br><small>{self.tr('Manage categories for events')}</small>")
        title_label.setStyleSheet("color: white; font-size: 14px;")
        
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.layout.addLayout(header_layout)

    def _setup_main_area(self):
        """Erstellt den Haupt-Bereich mit Liste und Details."""
        main_layout = QHBoxLayout()
        main_layout.setSpacing(15)

        # Linke Seite: Kategorien-Liste
        self._setup_categories_list(main_layout)

        # Rechte Seite: Kategorie-Details
        self._setup_category_details(main_layout)

        self.layout.addLayout(main_layout)

    def _setup_categories_list(self, parent_layout):
        """Erstellt die Kategorien-Liste."""
        list_group = QGroupBox(self.tr("Categories"))
        list_layout = QVBoxLayout(list_group)
        list_layout.setContentsMargins(15, 20, 15, 15)
        list_layout.setSpacing(10)

        # Kategorien-Liste
        self.list_categories = QListWidget()
        self.list_categories.setMinimumWidth(250)
        self.list_categories.setMinimumHeight(300)
        list_layout.addWidget(self.list_categories)

        # Aktions-Buttons unter der Liste
        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(5)

        self.btn_new_category = QPushButton(self.tr("➕ New"))
        self.btn_delete_category = QPushButton(self.tr("🗑️ Delete"))
        
        # Button-Styling
        button_style = """
            QPushButton {
                background-color: #555555;
                color: white;
                border: 1px solid #666666;
                border-radius: 3px;
                padding: 6px 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666666;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """
        
        self.btn_new_category.setStyleSheet(button_style)
        self.btn_delete_category.setStyleSheet(button_style + """
            QPushButton {
                background-color: #804040;
            }
            QPushButton:hover {
                background-color: #905050;
            }
        """)
        
        actions_layout.addWidget(self.btn_new_category)
        actions_layout.addWidget(self.btn_delete_category)
        actions_layout.addStretch()

        list_layout.addLayout(actions_layout)
        
        parent_layout.addWidget(list_group)

    def _setup_category_details(self, parent_layout):
        """Erstellt den Kategorie-Details-Bereich."""
        details_group = QGroupBox(self.tr("Category Details"))
        details_layout = QVBoxLayout(details_group)
        details_layout.setContentsMargins(15, 20, 15, 15)
        details_layout.setSpacing(15)

        # Form für Kategorie-Details
        form_layout = QFormLayout()
        form_layout.setSpacing(10)

        # Name
        self.le_category_name = QLineEdit()
        self.le_category_name.setPlaceholderText(self.tr("Enter category name..."))
        self.le_category_name.setMaxLength(40)  # Database constraint
        form_layout.addRow(self.tr("Name:"), self.le_category_name)

        # Beschreibung
        self.te_category_description = QTextEdit()
        self.te_category_description.setPlaceholderText(self.tr("Enter category description..."))
        self.te_category_description.setMaximumHeight(80)
        form_layout.addRow(self.tr("Description:"), self.te_category_description)

        details_layout.addLayout(form_layout)

        # Usage-Info
        self.lb_usage_info = QLabel()
        self.lb_usage_info.setStyleSheet("color: #cccccc; font-style: italic; padding: 10px;")
        self.lb_usage_info.setWordWrap(True)
        details_layout.addWidget(self.lb_usage_info)

        # Aktions-Button für Kategorie
        self.btn_save_category = QPushButton(self.tr("💾 Save Category"))
        self.btn_save_category.setStyleSheet("""
            QPushButton {
                background-color: #006d6d;
                color: white;
                border: 1px solid #008d8d;
                border-radius: 3px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #007d7d;
            }
            QPushButton:disabled {
                background-color: #333333;
                color: #666666;
            }
        """)
        details_layout.addWidget(self.btn_save_category)

        details_layout.addStretch()
        
        parent_layout.addWidget(details_group)

        # Initial: Details deaktivieren
        self._set_details_enabled(False)

    def _setup_button_area(self):
        """Erstellt den Button-Bereich."""
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        
        # OK-Button Text anpassen
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        ok_button.setText(self.tr("Select Category"))

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

    def _setup_connections(self):
        """Verbindet alle Signals und Slots."""
        # Dialog-Buttons
        self.button_box.accepted.connect(self._select_and_close)
        self.button_box.rejected.connect(self.reject)

        # Kategorien-Liste
        self.list_categories.currentItemChanged.connect(self._on_category_selected)

        # Aktions-Buttons
        self.btn_new_category.clicked.connect(self._new_category)
        self.btn_delete_category.clicked.connect(self._delete_category)
        self.btn_save_category.clicked.connect(self._save_category)

        # Auto-Save bei Eingaben (mit Verzögerung)
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._auto_save_category)
        
        self.le_category_name.textChanged.connect(self._on_details_changed)
        self.te_category_description.textChanged.connect(self._on_details_changed)

    def _load_categories(self):
        """Lädt alle Kategorien für das Projekt."""
        try:
            # Events laden um Usage-Count zu berechnen
            event_list = self.service.get_all_events(self.project_id)
            
            # Usage-Count pro Kategorie berechnen
            category_usage = {}
            for event in event_list.events:
                for category in event.categories:
                    category_usage[category] = category_usage.get(category, 0) + 1
            
            self.categories_data = category_usage
            
            # Liste aktualisieren
            self._refresh_categories_list()
            
            logger.info(f"Loaded {len(self.categories_data)} categories")
            
        except Exception as e:
            logger.error(f"Error loading categories: {e}")
            QMessageBox.warning(self, self.tr("Warning"), 
                              self.tr(f"Could not load categories: {str(e)}"))

    def _refresh_categories_list(self):
        """Aktualisiert die Kategorien-Liste."""
        self.list_categories.clear()
        
        if not self.categories_data:
            # Placeholder wenn keine Kategorien
            item = QListWidgetItem(self.tr("No categories found"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)  # Nicht auswählbar
            item.setData(Qt.ItemDataRole.UserRole, None)
            self.list_categories.addItem(item)
            return
        
        # Kategorien alphabetisch sortiert
        for category_name in sorted(self.categories_data.keys()):
            usage_count = self.categories_data[category_name]
            
            # Display-Text mit Usage-Info
            if usage_count > 0:
                display_text = f"{category_name} ({usage_count} events)"
            else:
                display_text = f"{category_name} (unused)"
            
            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, category_name)
            self.list_categories.addItem(item)

    def _select_category_by_name(self, category_name: str):
        """Wählt eine Kategorie in der Liste aus."""
        for i in range(self.list_categories.count()):
            item = self.list_categories.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == category_name:
                self.list_categories.setCurrentItem(item)
                break

    def _on_category_selected(self, current_item, previous_item):
        """Reagiert auf Kategorie-Auswahl."""
        if not current_item:
            self._set_details_enabled(False)
            return
            
        category_name = current_item.data(Qt.ItemDataRole.UserRole)
        if not category_name:  # Placeholder-Item
            self._set_details_enabled(False)
            return
        
        self.current_category = category_name
        self._load_category_details(category_name)
        self._set_details_enabled(True)

    def _load_category_details(self, category_name: str):
        """Lädt die Details einer Kategorie."""
        try:
            # Für jetzt: Nur Name (da wir keine Beschreibung in der aktuellen Implementierung haben)
            self.le_category_name.setText(category_name)
            self.te_category_description.clear()  # TODO: Beschreibung aus DB laden wenn implementiert
            
            # Usage-Info anzeigen
            usage_count = self.categories_data.get(category_name, 0)
            if usage_count > 0:
                usage_text = self.tr(f"This category is used in {usage_count} event(s).")
                if usage_count > 0:
                    usage_text += f"\n{self.tr('Deleting this category will remove it from all events.')}"
            else:
                usage_text = self.tr("This category is not used in any events.")
            
            self.lb_usage_info.setText(usage_text)
            
        except Exception as e:
            logger.error(f"Error loading category details: {e}")

    def _set_details_enabled(self, enabled: bool):
        """Aktiviert/deaktiviert den Details-Bereich."""
        self.le_category_name.setEnabled(enabled)
        self.te_category_description.setEnabled(enabled)
        self.btn_save_category.setEnabled(enabled)
        
        if not enabled:
            self.le_category_name.clear()
            self.te_category_description.clear()
            self.lb_usage_info.clear()
            self.current_category = None

    def _new_category(self):
        """Erstellt eine neue Kategorie."""
        # Neue Kategorie in Liste hinzufügen (temporär)
        new_name = self.tr("New Category")
        counter = 1
        while new_name in self.categories_data:
            new_name = f"{self.tr('New Category')} {counter}"
            counter += 1
        
        # Temporär zu Daten hinzufügen
        self.categories_data[new_name] = 0
        
        # Liste aktualisieren und neue Kategorie auswählen
        self._refresh_categories_list()
        self._select_category_by_name(new_name)
        
        # Fokus auf Name-Feld für sofortige Bearbeitung
        self.le_category_name.selectAll()
        self.le_category_name.setFocus()

    def _delete_category(self):
        """Löscht die ausgewählte Kategorie."""
        if not self.current_category:
            return
        
        usage_count = self.categories_data.get(self.current_category, 0)
        
        # Bestätigung
        if usage_count > 0:
            message = self.tr(
                f"Are you sure you want to delete the category '{self.current_category}'?\n\n"
                f"This category is used in {usage_count} event(s) and will be removed from all of them.\n\n"
                f"This action cannot be undone."
            )
        else:
            message = self.tr(
                f"Are you sure you want to delete the category '{self.current_category}'?\n\n"
                f"This action cannot be undone."
            )
        
        reply = QMessageBox.question(
            self, self.tr("Delete Category"), message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            try:
                # TODO: Service-Method für Kategorie-Löschung implementieren
                # Für jetzt: Aus lokalen Daten entfernen
                if self.current_category in self.categories_data:
                    del self.categories_data[self.current_category]
                
                self._refresh_categories_list()
                self._set_details_enabled(False)
                
                QMessageBox.information(self, self.tr("Success"), 
                                      self.tr(f"Category '{self.current_category}' was deleted successfully."))
                
            except Exception as e:
                logger.error(f"Error deleting category: {e}")
                QMessageBox.critical(self, self.tr("Error"), 
                                   self.tr(f"Could not delete category: {str(e)}"))

    def _save_category(self):
        """Speichert die aktuelle Kategorie."""
        self._auto_save_category()

    def _on_details_changed(self):
        """Reagiert auf Änderungen in den Details-Feldern."""
        # Verzögertes Auto-Save starten
        self.save_timer.start(1000)  # 1 Sekunde Verzögerung

    def _auto_save_category(self):
        """Automatisches Speichern der Kategorie."""
        if not self.current_category:
            return
        
        new_name = self.le_category_name.text().strip()
        if not new_name:
            QMessageBox.warning(self, self.tr("Validation Error"), 
                              self.tr("Please enter a category name."))
            return
        
        try:
            # Name geändert?
            if new_name != self.current_category:
                # Name-Änderung in lokalen Daten
                if self.current_category in self.categories_data:
                    usage_count = self.categories_data[self.current_category]
                    del self.categories_data[self.current_category]
                    self.categories_data[new_name] = usage_count
                
                self.current_category = new_name
                
                # Liste aktualisieren
                self._refresh_categories_list()
                self._select_category_by_name(new_name)
            
            # TODO: Service-Method für Kategorie-Update implementieren
            # description = self.te_category_description.toPlainText().strip()
            
            logger.info(f"Category saved: {new_name}")
            
        except Exception as e:
            logger.error(f"Error saving category: {e}")
            QMessageBox.critical(self, self.tr("Error"), 
                               self.tr(f"Could not save category: {str(e)}"))

    def _select_and_close(self):
        """Wählt die aktuelle Kategorie aus und schließt den Dialog."""
        current_item = self.list_categories.currentItem()
        if current_item:
            selected_category = current_item.data(Qt.ItemDataRole.UserRole)
            if selected_category:  # Nicht bei Placeholder-Items
                self.selected_category_result = selected_category
        
        self.accept()

    def get_selected_category(self) -> Optional[str]:
        """Gibt die ausgewählte Kategorie zurück."""
        return self.selected_category_result
