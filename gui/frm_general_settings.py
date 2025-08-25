import os

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout, QSpinBox,
                               QDialogButtonBox, QComboBox)

from configuration.general_settings import general_settings_handler
from gui.custom_widgets import date_format_selector
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import setup_form_help


class DlgGeneralSettings(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle(self.tr("General Settings"))
        self._setup_ui()
        self._setup_data()
        setup_form_help(self, "general_settings")

    def _setup_ui(self):
        self.layout = QVBoxLayout(self)
        self.layout_head = QVBoxLayout()
        self.layout_body = QVBoxLayout()
        self.layout_body.setContentsMargins(0, 10, 0, 0)
        self.layout_foot = QVBoxLayout()
        self.layout.addLayout(self.layout_head)
        self.layout.addLayout(self.layout_body)
        self.layout.addLayout(self.layout_foot)

        self.lb_description = QLabel(self.tr('<h4>System wide settings</h4>'
                                             '<p>Changes only become effective after a restart.</p>'))
        self.layout_head.addWidget(self.lb_description)
        self.group_plan = QGroupBox(self.tr('Schedules'))
        self.layout_body.addWidget(self.group_plan)
        self.layout_group_plan = QFormLayout(self.group_plan)
        self.group_language = QGroupBox(self.tr('Interface Language'))
        self.layout_body.addWidget(self.group_language)
        self.layout_group_language = QFormLayout(self.group_language)
        self.group_date_format = QGroupBox(self.tr('Date and time format'))
        self.layout_body.addWidget(self.group_date_format)
        self.layout_group_date_format = QVBoxLayout(self.group_date_format)
        self.spin_column_width = QSpinBox()
        self.spin_column_width.setMinimum(100)
        self.spin_column_width.setMaximum(500)
        self.spin_column_width_statistics = QSpinBox()
        self.spin_column_width_statistics.setMinimum(50)
        self.spin_column_width_statistics.setMaximum(500)
        self.layout_group_plan.addRow(self.tr('Column width schedules:'), self.spin_column_width)
        self.layout_group_plan.addRow(self.tr('Column width statistics:'), self.spin_column_width_statistics)
        self.combo_language = QComboBox()
        self.layout_group_language.addRow(self.tr('Language:'), self.combo_language)
        self.date_format_selector = date_format_selector.LocaleSelector()
        self.layout_group_date_format.addWidget(self.date_format_selector)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.layout_foot.addWidget(self.button_box)

    def _setup_data(self):
        self.general_settings = general_settings_handler.get_general_settings()
        self.spin_column_width.setValue(self.general_settings.plan_settings.column_width_plan)
        self.spin_column_width_statistics.setValue(self.general_settings.plan_settings.column_width_statistics)
        folder_translations = os.path.join(os.path.dirname(__file__), 'translations')
        for file in sorted(os.listdir(folder_translations)):
            if file.endswith('.qm'):
                string_language = file.split('_')[1].split('.')[0]
                self.combo_language.addItem(string_language, string_language)
        if self.general_settings.language:
            self.combo_language.setCurrentIndex(self.combo_language.findData(self.general_settings.language))
        else:
            self.combo_language.setCurrentIndex(self.combo_language.findData('en'))

    def accept(self):
        self.general_settings.plan_settings.column_width_plan = self.spin_column_width.value()
        self.general_settings.plan_settings.column_width_statistics = self.spin_column_width_statistics.value()
        self.general_settings.language = self.combo_language.currentData()
        self.date_format_selector.save_settings()
        general_settings_handler.save_to_toml_file(self.general_settings)
        super().accept()
