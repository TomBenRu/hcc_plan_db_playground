from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout, QSpinBox,
                               QDialogButtonBox)

from configuration.general_settings import general_settings_handler


class DlgGeneralSettings(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle("General Settings")
        self._setup_ui()
        self._setup_data()

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel('<h4>Systemweite Einstellungen</h4>'
                                     '<p>Änderungen werden erst nach einem Neustart wirksam.</p>')
        self.layout_head.addWidget(self.lb_description)
        self.group_plan = QGroupBox('Plan')
        self.layout_body.addWidget(self.group_plan)
        self.layout_group_plan = QFormLayout(self.group_plan)
        self.spin_column_width = QSpinBox()
        self.spin_column_width.setMinimum(100)
        self.spin_column_width.setMaximum(500)
        self.layout_group_plan.addRow('Spaltenbreite:', self.spin_column_width)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_data(self):
        self.general_settings = general_settings_handler.get_general_settings()
        self.spin_column_width.setValue(self.general_settings.plan_settings.column_width)

    def accept(self):
        self.general_settings.plan_settings.column_width = self.spin_column_width.value()
        general_settings_handler.save_to_toml_file(self.general_settings)
        super().accept()
