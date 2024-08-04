from uuid import UUID

from PySide6.QtWidgets import (QDialog, QWidget, QLabel, QPushButton, QGridLayout, QDialogButtonBox, QVBoxLayout,
                               QGroupBox, QColorDialog)

from database import schemas, db_services


class DlgExcelExportSettings(QDialog):
    def __init__(self, parent: QWidget, excel_settings: schemas.ExcelExportSettings,
                 former_object_containing_settings: schemas.ModelWithExcelSettings = None):
        super().__init__(parent)
        self.setWindowTitle('Excel-Export-Settings')

        self.former_object_containing_settings = former_object_containing_settings
        self.excel_settings = excel_settings.model_copy()
        self.curr_excel_settings_id: UUID = excel_settings.id

        self.layout = QVBoxLayout(self)

        self.group_top = QGroupBox('Überschriften')
        self.group_side = QGroupBox('Kalenderwochen')
        self.group_body = QGroupBox('Tagesdatum')

        self.layout.addWidget(self.group_top)
        self.layout.addWidget(self.group_side)
        self.layout.addWidget(self.group_body)

        self.layout_group_top = QGridLayout(self.group_top)
        self.layout_group_side = QGridLayout(self.group_side)
        self.layout_group_body = QGridLayout(self.group_body)

        if self.former_object_containing_settings:
            self.bt_reset = QPushButton(f'reset to {former_object_containing_settings.name}')
            self.bt_reset.clicked.connect(self.reset_to_former_object)
            self.layout.addWidget(self.bt_reset)

        self.buttons_color: dict[str, QPushButton] = {}

        self.autofill()

        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def autofill(self):
        for i, (key, val) in enumerate(self.excel_settings.model_dump(exclude={'id'}).items()):
            label = QLabel(key)
            self.buttons_color[key] = QPushButton()
            self.buttons_color[key].clicked.connect(self.get_color)
            self.buttons_color[key].setObjectName(key)
            self.buttons_color[key].setStyleSheet(f'background-color: {val}')
            if i < 4:
                self.layout_group_top.addWidget(label, i, 0)
                self.layout_group_top.addWidget(self.buttons_color[key], i, 1)
            elif i < 6:
                self.layout_group_body.addWidget(label, i-4, 0)
                self.layout_group_body.addWidget(self.buttons_color[key], i-4, 1)
            else:
                self.layout_group_side.addWidget(label, i-6, 0)
                self.layout_group_side.addWidget(self.buttons_color[key], i-6, 1)

    def get_color(self):
        widget = self.sender()
        current_color = self.excel_settings.__getattribute__(widget.objectName())
        color_dialog = QColorDialog()

        bt_color = color_dialog.getColor(current_color, self, None)

        if bt_color.isValid():
            widget.setStyleSheet(f"background-color : {bt_color.name()}")
            self.excel_settings.__setattr__(widget.objectName(), bt_color.name())

        # Bei einer Änderung einer Farbe wird die aktuelle Excel-Settings-ID auf die ID der ursprünglichen
        # Excel-Settings gesetzt, falls diese nicht zu den Excel-Settings des übergeordneten Objekts gehört. Andernfalls
        # wird die aktuelle Excel-Settings-ID auf None gesetzt, was bedeutet, dass neue Excel-Settings mit den aktuellen
        # Einstellungen für das aktuelle Objekt erstellt werden sollen:
        self.curr_excel_settings_id = (
            self.excel_settings.id
            if self.excel_settings.id != self.former_object_containing_settings.excel_export_settings.id else None)

    def reset_to_former_object(self):
        for key, color in self.former_object_containing_settings.excel_export_settings.model_dump(exclude={'id'}).items():
            self.buttons_color[key].setStyleSheet(f"background-color : {color}")
            self.excel_settings.__setattr__(key, color)

        # Durch Setzen der aktuellen Excel-Settings-ID auf die ID der Excel-Settings des übergeordneten Objekts wird
        # angezeigt, dass die Excel-Settings des aktuellen Objekts auf die des übergeordneten Objekts zurückgesetzt
        # wurden. Das aktuelle Objekt soll also mit den Excel-Settings des übergeordneten Objekts aktualisiert werden.
        self.curr_excel_settings_id = self.former_object_containing_settings.excel_export_settings.id
