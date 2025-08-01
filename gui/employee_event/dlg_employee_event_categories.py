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

from commands import command_base_classes
from employee_event import EmployeeEventService, ErrorResponseSchema, CategoryDetail, CategoryCreate, CategoryUpdate
from employee_event.db_commands import category_commands

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

    def __init__(self, parent: QWidget, project_id: UUID, selected_category_id: Optional[UUID] = None):
        super().__init__(parent=parent)

        self.project_id = project_id
        self.selected_category_id = selected_category_id

        self.controller = command_base_classes.ContrExecUndoRedo()
        self.service = EmployeeEventService()
        
        # Daten-Cache
        self.categories_data: list[CategoryDetail] = []
        self.category_usage: dict[str, int] = {}
        self.current_category: CategoryDetail | None = None
        
        # Return-Wert für aufrufenden Dialog
        self.selected_category_result: CategoryDetail | None = None
        
        self._setup_ui()
        self._setup_connections()
        self._load_categories()
        
        # Vorausgewählte Kategorie setzen
        if selected_category_id:
            self._select_category_by_id(selected_category_id)
            
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

    def _load_categories(self):
        """Lädt alle Kategorien für das Projekt."""
        try:
            # Events laden um Usage-Count zu berechnen
            event_list = self.service.get_all_events(self.project_id)

            self.categories_data = sorted(
                self.service.get_all_categories_by_project(self.project_id),
                key=lambda c: c.name
            )
            
            # Usage-Count pro Kategorie berechnen
            self.category_usage = {c.name: 0 for c in self.categories_data}
            for event in event_list:
                for category in event.categories:
                    self.category_usage[category.name] += 1
            
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

        for category in self.categories_data:
            usage_count = self.category_usage[category.name]

            # Display-Text mit Usage-Info
            if usage_count > 0:
                display_text = f"{category.name} ({usage_count} events)"
            else:
                display_text = f"{category.name} (unused)"

            item = QListWidgetItem(display_text)
            item.setData(Qt.ItemDataRole.UserRole, category)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.list_categories.addItem(item)

    def _select_category_by_id(self, category_id: UUID):
        """Wählt eine Kategorie in der Liste aus."""
        for i in range(self.list_categories.count()):
            item = self.list_categories.item(i)
            item_data = item.data(Qt.ItemDataRole.UserRole)
            if item_data and item_data.id == category_id:
                self.list_categories.setCurrentItem(item)
                break

    def _on_category_selected(self, current_item: QListWidgetItem, previous_item):
        """Reagiert auf Kategorie-Auswahl."""
        print("Current Item:", current_item)
        print("Previous Item:", previous_item)
        print(f'{self.current_category=}')
        if not current_item:
            self._set_details_enabled(False)
            return
            
        category_text = current_item.text()
        if not category_text:  # Placeholder-Item
            self._set_details_enabled(False)
            return
        
        self.current_category = current_item.data(Qt.ItemDataRole.UserRole)
        self._load_category_details(self.current_category)
        self._set_details_enabled(True)

    def _load_category_details(self, category: CategoryDetail):
        """Lädt die Details einer Kategorie."""
        try:
            # Für jetzt: Nur Name (da wir keine Beschreibung in der aktuellen Implementierung haben)
            self.le_category_name.setText(category.name)
            self.te_category_description.clear()
            self.te_category_description.append(category.description)
            
            # Usage-Info anzeigen
            usage_count = self.category_usage.get(category.name, 0)
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
        # # Neue Kategorie in Liste hinzufügen (temporär)
        # new_name = self.tr("New Category")
        # counter = 1
        # while new_name in self.categories_data:
        #     new_name = f"{self.tr('New Category')} {counter}"
        #     counter += 1
        #
        # # Temporär zu Daten hinzufügen
        # self.categories_data[new_name] = 0
        #
        # # Liste aktualisieren und neue Kategorie auswählen
        # self._refresh_categories_list()
        # self._select_category_by_id(new_name)
        
        # Fokus auf Name-Feld für sofortige Bearbeitung
        self.current_category = None
        self.list_categories.clearSelection()
        self._set_details_enabled(True)
        self.le_category_name.clear()
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

        new_name = self.le_category_name.text().strip()
        if not new_name:
            QMessageBox.warning(self, self.tr("Validation Error"), 
                              self.tr("Please enter a category name."))
            return
        
        try:
            # falls eine neue Kategorie erstellt werden soll
            if not self.current_category:
                if new_name in [c.name for c in self.categories_data]:
                    QMessageBox.warning(self, self.tr("Validation Error"),
                                      self.tr("A category with this name already exists."))
                    return
                category_create = CategoryCreate(
                    name=new_name,
                    description=self.te_category_description.toPlainText().strip(),
                    project_id=self.project_id
                )
                command = category_commands.Create(category_create)
                self.controller.execute(command)

                if isinstance(command.result, ErrorResponseSchema):
                    QMessageBox.critical(self, self.tr("Error"),
                                       self.tr(f"Could not create category: {command.result.message}"))
                    return

                self.categories_data.append(command.result)
                self.category_usage[new_name] = 0
                self._refresh_categories_list()
                self._select_category_by_id(command.result.id)
            
                logger.info(f"Category saved: {new_name}")

            else:
                # falls eine bestehende Kategorie aktualisiert werden soll
                category_update = CategoryUpdate(
                    id=self.current_category.id,
                    name=new_name,
                    description=self.te_category_description.toPlainText().strip()
                )
                command = category_commands.Update(category_update)
                self.controller.execute(command)

                if isinstance(command.result, ErrorResponseSchema):
                    QMessageBox.critical(self, self.tr("Error"),
                                       self.tr(f"Could not update category: {command.result.message}"))
                    return

                index = [c.id for c in self.categories_data].index(self.current_category.id)
                old_name = self.categories_data[index].name
                self.category_usage[new_name] = self.category_usage.pop(old_name)
                self.categories_data[index] = command.result
                self._refresh_categories_list()
                self._select_category_by_id(command.result.id)
            
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

    def get_selected_category(self) -> Optional[CategoryDetail]:
        """Gibt die ausgewählte Kategorie zurück."""
        return self.selected_category_result

    def reject(self, /):
        self.controller.undo_all()
        super().reject()
