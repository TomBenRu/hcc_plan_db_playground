from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog, QWidget, QLabel, QLineEdit, QTimeEdit, QPushButton, QGridLayout, QMessageBox, \
    QDialogButtonBox, QCheckBox, QVBoxLayout, QGroupBox, QColorDialog, QMainWindow

from database import schemas


class FrmExcelExportSettings(QDialog):
    def __init__(self, parent: QWidget, excel_settings: schemas.ExcelExportSettings):
        super().__init__(parent)
        self.setWindowTitle('Exce-Export-Settings')

        self.excel_settings = excel_settings.copy()

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

        self.autofill()

        self.button_box = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout.addWidget(self.button_box)

    def autofill(self):
        for i, (key, val) in enumerate(self.excel_settings.dict(exclude={'id'}).items()):
            label = QLabel(key)
            label.width
            button = QPushButton()
            button.clicked.connect(self.get_color)
            button.setObjectName(key)
            button.setStyleSheet(f'background-color: {val}')
            if i < 4:
                self.layout_group_top.addWidget(label, i, 0)
                self.layout_group_top.addWidget(button, i, 1)
            elif i < 6:
                self.layout_group_body.addWidget(label, i-4, 0)
                self.layout_group_body.addWidget(button, i-4, 1)
            else:
                self.layout_group_side.addWidget(label, i-6, 0)
                self.layout_group_side.addWidget(button, i-6, 1)

    def get_color(self):
        widget = self.sender()
        current_color = self.excel_settings.__getattribute__(widget.objectName())
        color_dialog = QColorDialog()

        bt_color = color_dialog.getColor(current_color, self, None)

        if bt_color.isValid():
            widget.setStyleSheet(f"background-color : {bt_color.name()}")
            self.excel_settings.__setattr__(widget.objectName(), bt_color.name())
