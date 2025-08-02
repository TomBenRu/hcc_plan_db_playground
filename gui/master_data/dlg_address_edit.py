"""
Address Edit Dialog - Shared component for CRUD operations on addresses.

This dialog can be used by multiple modules:
- Employee Event Management (for event locations)
- Person Management (for employee addresses)
- LocationOfWork Management (for workplace addresses)

Features:
- CRUD modes: Create/Update/Delete in one dialog
- Mode detection: Automatic based on address_id parameter
- Form fields: Street, Postal Code, City
- Dark theme: Consistent with app.py styles
- Commands integration: Uses address_commands for Undo/Redo
- Returns: created_address_id or updated_address_id
"""

from uuid import UUID
from typing import Optional

from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                               QLineEdit, QPushButton, QLabel, QMessageBox, QFrame, QWidget)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from database import schemas
from commands.database_commands import address_commands
from commands.command_base_classes import ContrExecUndoRedo


class DlgAddressEdit(QDialog):
    """
    CRUD Dialog for Address management.
    
    Usage:
    - Create Mode: DlgAddressEdit(parent=self)
    - Edit Mode: DlgAddressEdit(parent=self, address_id=existing_id)
    - Returns: created_address_id or updated_address_id via get_result()
    """
    
    # Signals
    address_saved = Signal(UUID)  # Emitted when address is successfully saved
    address_deleted = Signal(UUID)  # Emitted when address is successfully deleted
    
    def __init__(self, parent: QWidget, project_id: UUID, address_id: Optional[UUID] = None):
        super().__init__(parent)
        
        # State
        self.project_id = project_id
        self.address_id = address_id
        self.address_data: Optional[schemas.Address] = None
        self.result_id: Optional[UUID] = None
        self.command_controller = ContrExecUndoRedo()
        
        # Mode detection
        self.is_edit_mode = address_id is not None
        
        # Initialize
        self._setup_ui()
        self._setup_styling()
        self._setup_connections()
        
        if self.is_edit_mode:
            self._load_address_data()
        
        self._update_ui_for_mode()
    
    def _setup_ui(self):
        """Setup the user interface."""
        self.setModal(True)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # Title
        self.lbl_title = QLabel()
        self.lbl_title.setAlignment(Qt.AlignCenter)
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.lbl_title.setFont(font)
        main_layout.addWidget(self.lbl_title)
        
        # Form section
        form_frame = QFrame()
        form_layout = QFormLayout(form_frame)
        form_layout.setSpacing(10)
        
        # Form fields
        self.le_street = QLineEdit()
        self.le_street.setPlaceholderText("z.B. Musterstraße 123")
        self.le_postal_code = QLineEdit()
        self.le_postal_code.setPlaceholderText("z.B. 12345")
        self.le_city = QLineEdit()
        self.le_city.setPlaceholderText("z.B. Berlin")
        
        # Add to form
        form_layout.addRow("Straße:", self.le_street)
        form_layout.addRow("Postleitzahl:", self.le_postal_code)
        form_layout.addRow("Stadt:", self.le_city)
        
        main_layout.addWidget(form_frame)
        
        # Button section
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        self.btn_save = QPushButton("Speichern")
        self.btn_save.setDefault(True)
        self.btn_delete = QPushButton("Löschen")
        self.btn_cancel = QPushButton("Abbrechen")
        
        button_layout.addWidget(self.btn_save)
        button_layout.addWidget(self.btn_delete)
        button_layout.addStretch()
        button_layout.addWidget(self.btn_cancel)
        
        main_layout.addLayout(button_layout)
    
    def _setup_styling(self):
        """Apply dark theme styling consistent with the app."""
        # Main dialog styling
        self.setStyleSheet("""
            QDialog {
                background-color: #2b2b2b;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
                font-size: 10pt;
            }
            QLineEdit {
                background-color: #3c3c3c;
                border: 1px solid #555555;
                border-radius: 3px;
                padding: 5px;
                color: #ffffff;
                font-size: 10pt;
                min-height: 25px;
            }
            QLineEdit:focus {
                border: 2px solid #0078d4;
            }
            QPushButton {
                background-color: #0078d4;
                border: none;
                border-radius: 3px;
                color: white;
                padding: 8px 16px;
                font-size: 10pt;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #106ebe;
            }
            QPushButton:pressed {
                background-color: #005a9e;
            }
            QPushButton#btn_delete {
                background-color: #d13438;
            }
            QPushButton#btn_delete:hover {
                background-color: #b71c1c;
            }
            QFrame {
                background-color: transparent;
            }
        """)
        
        # Set object names for specific styling
        self.btn_delete.setObjectName("btn_delete")
    
    def _setup_connections(self):
        """Setup signal connections."""
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_delete.clicked.connect(self._on_delete_clicked)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Enable Enter key for save
        self.le_street.returnPressed.connect(self._on_save_clicked)
        self.le_postal_code.returnPressed.connect(self._on_save_clicked)
        self.le_city.returnPressed.connect(self._on_save_clicked)
    
    def _load_address_data(self):
        """Load existing address data for edit mode."""
        try:
            from database import db_services
            self.address_data = db_services.Address.get(self.address_id)
            
            # Populate form fields
            self.le_street.setText(self.address_data.street)
            self.le_postal_code.setText(self.address_data.postal_code)
            self.le_city.setText(self.address_data.city)
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Adresse konnte nicht geladen werden:\n{str(e)}")
            self.reject()
    
    def _update_ui_for_mode(self):
        """Update UI elements based on create/edit mode."""
        if self.is_edit_mode:
            self.setWindowTitle("Adresse bearbeiten")
            self.lbl_title.setText("Adresse bearbeiten")
            self.btn_delete.setVisible(True)
        else:
            self.setWindowTitle("Neue Adresse")
            self.lbl_title.setText("Neue Adresse erstellen")
            self.btn_delete.setVisible(False)
    
    def _validate_input(self) -> bool:
        """Validate user input."""
        if not self.le_street.text().strip():
            QMessageBox.warning(self, "Eingabefehler", "Bitte geben Sie eine Straße ein.")
            self.le_street.setFocus()
            return False
        
        if not self.le_postal_code.text().strip():
            QMessageBox.warning(self, "Eingabefehler", "Bitte geben Sie eine Postleitzahl ein.")
            self.le_postal_code.setFocus()
            return False
        
        if not self.le_city.text().strip():
            QMessageBox.warning(self, "Eingabefehler", "Bitte geben Sie eine Stadt ein.")
            self.le_city.setFocus()
            return False
        
        return True
    
    def _create_address_schema(self) -> schemas.AddressCreate:
        """Create AddressCreate schema from form data."""
        return schemas.AddressCreate(
            project_id=self.project_id,
            street=self.le_street.text().strip(),
            postal_code=self.le_postal_code.text().strip(),
            city=self.le_city.text().strip()
        )
    
    def _create_address_update_schema(self) -> schemas.Address:
        """Create Address schema for update from form data."""
        return schemas.Address(
            id=self.address_id,
            street=self.le_street.text().strip(),
            postal_code=self.le_postal_code.text().strip(),
            city=self.le_city.text().strip(),
            project=self.address_data.project
        )
    
    def _on_save_clicked(self):
        """Handle save button click."""
        if not self._validate_input():
            return
        
        try:
            if self.is_edit_mode:
                self._update_address()
            else:
                self._create_address()
                
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Adresse konnte nicht gespeichert werden:\n{str(e)}")
    
    def _create_address(self):
        """Create a new address."""
        address_create = self._create_address_schema()
        
        # Execute command
        command = address_commands.Create(address_create)
        self.command_controller.execute(command)
        
        # Store result
        self.result_id = command.created_address.id
        
        # Emit signal
        self.address_saved.emit(self.result_id)
    
    def _update_address(self):
        """Update existing address."""
        address_update = self._create_address_update_schema()
        
        # Execute command
        command = address_commands.Update(address_update)
        self.command_controller.execute(command)
        
        # Store result
        self.result_id = self.address_id
        
        # Emit signal
        self.address_saved.emit(self.result_id)
    
    def _on_delete_clicked(self):
        """Handle delete button click."""
        if not self.is_edit_mode:
            return
        
        # Confirmation dialog
        reply = QMessageBox.question(
            self, 
            "Adresse löschen",
            f"Möchten Sie die Adresse wirklich löschen?\n\n"
            f"Straße: {self.address_data.street}\n"
            f"Stadt: {self.address_data.city}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # Execute delete command
                command = address_commands.Delete(self.address_id)
                self.command_controller.execute(command)
                
                # Emit signal
                self.address_deleted.emit(self.address_id)
                
                self.accept()
                
            except Exception as e:
                QMessageBox.critical(self, "Fehler", f"Adresse konnte nicht gelöscht werden:\n{str(e)}")
    
    def get_result(self) -> Optional[UUID]:
        """
        Get the result ID after dialog completion.
        
        Returns:
            UUID: The ID of the created or updated address, or None if cancelled/failed
        """
        return self.result_id
    
    def undo_last_operation(self):
        """Undo the last operation (useful for testing or external undo functionality)."""
        self.command_controller.undo()
    
    def redo_last_operation(self):
        """Redo the last operation (useful for testing or external redo functionality)."""
        self.command_controller.redo()


# Convenience functions for easy usage
def create_address_dialog(parent=None) -> Optional[UUID]:
    """
    Show a dialog to create a new address.
    
    Returns:
        UUID: The ID of the created address, or None if cancelled
    """
    dialog = DlgAddressEdit(parent)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_result()
    return None


def edit_address_dialog(parent=None, address_id: UUID = None) -> Optional[UUID]:
    """
    Show a dialog to edit an existing address.
    
    Args:
        parent: Parent widget
        address_id: ID of the address to edit
    
    Returns:
        UUID: The ID of the updated address, or None if cancelled
    """
    if not address_id:
        return None
        
    dialog = DlgAddressEdit(parent, address_id)
    if dialog.exec() == QDialog.DialogCode.Accepted:
        return dialog.get_result()
    return None
