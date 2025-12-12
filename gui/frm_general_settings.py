import os
import platform

from PySide6.QtWidgets import (QDialog, QWidget, QVBoxLayout, QLabel, QGroupBox, QFormLayout, QSpinBox,
                               QDialogButtonBox, QComboBox, QPushButton, QMessageBox, QHBoxLayout)

from configuration.general_settings import general_settings_handler
from gui.custom_widgets import date_format_selector
from gui.custom_widgets.excel_folder_date_format_selector import ExcelFolderDateFormatSelector
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData
from tools.helper_functions import setup_form_help


class DlgGeneralSettings(QDialog):
    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setWindowTitle(self.tr("General Settings"))
        self._setup_ui()
        self._setup_data()
        setup_form_help(self, "general_settings", add_help_button=True)

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

        # Windows Defender Settings (nur auf Windows)
        if platform.system() == "Windows":
            self.group_defender = QGroupBox(self.tr('Performance'))
            self.layout_body.addWidget(self.group_defender)
            self.layout_group_defender = QVBoxLayout(self.group_defender)

            # Beschreibung
            self.lb_defender_description = QLabel(
                self.tr('You can exclude this application from Windows Defender scanning '
                        'to speed up the program startup.')
            )
            self.lb_defender_description.setWordWrap(True)
            self.layout_group_defender.addWidget(self.lb_defender_description)

            # Status und Button in horizontalem Layout
            status_button_layout = QHBoxLayout()

            # Status-Label
            self.lb_defender_status = QLabel()
            status_button_layout.addWidget(self.lb_defender_status)
            status_button_layout.addStretch()

            # Button
            self.btn_add_defender_exclusion = QPushButton(self.tr('Exclude from virus scan'))
            self.btn_add_defender_exclusion.clicked.connect(self._on_add_defender_exclusion)
            status_button_layout.addWidget(self.btn_add_defender_exclusion)

            self.layout_group_defender.addLayout(status_button_layout)
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

        # Excel-Ordner Datumsformat
        self.group_excel_folder_date = QGroupBox(self.tr('Excel Export Folder Format'))
        self.layout_body.addWidget(self.group_excel_folder_date)
        self.layout_group_excel_folder_date = QVBoxLayout(self.group_excel_folder_date)
        self.excel_folder_date_selector = ExcelFolderDateFormatSelector()
        self.layout_group_excel_folder_date.addWidget(self.excel_folder_date_selector)

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

        # Windows Defender Status aktualisieren (nur auf Windows)
        if platform.system() == "Windows":
            self._update_defender_status()

    def _update_defender_status(self):
        """
        Aktualisiert die Anzeige des Windows Defender-Status.

        Zeigt an, ob die Anwendung bereits vom Defender ausgeschlossen ist.
        Kann nur mit Admin-Rechten geprüft werden.
        """
        try:
            from tools.windows_defender_utils import is_admin, check_defender_exclusion

            if is_admin():
                # Mit Admin-Rechten: Status kann geprüft werden
                is_excluded = check_defender_exclusion()

                if is_excluded:
                    self.lb_defender_status.setText(self.tr('✓ Excluded from virus scanning'))
                    self.lb_defender_status.setStyleSheet('color: green; font-weight: bold;')
                    self.btn_add_defender_exclusion.setEnabled(False)
                    self.btn_add_defender_exclusion.setText(self.tr('Already excluded'))
                else:
                    self.lb_defender_status.setText(self.tr('Not excluded'))
                    self.lb_defender_status.setStyleSheet('color: orange;')
                    self.btn_add_defender_exclusion.setEnabled(True)
                    self.btn_add_defender_exclusion.setText(self.tr('Exclude from virus scan'))
            else:
                # Ohne Admin-Rechte: Status kann nicht geprüft werden
                self.lb_defender_status.setText(
                    self.tr('Status unknown (admin rights required)')
                )
                self.lb_defender_status.setStyleSheet('color: gray;')
                self.btn_add_defender_exclusion.setEnabled(True)
                self.btn_add_defender_exclusion.setText(self.tr('Exclude from virus scan'))

        except Exception as e:
            # Fehler beim Status-Check
            self.lb_defender_status.setText(self.tr('Error checking status'))
            self.lb_defender_status.setStyleSheet('color: red;')

    def _on_add_defender_exclusion(self):
        """
        Handler für den "Vom Virenscan ausschließen" Button.

        Zeigt Bestätigungsdialog und führt die Ausnahme hinzu.
        Aktualisiert anschließend den Status.
        """
        try:
            from tools.windows_defender_utils import add_defender_exclusion

            # Bestätigungsdialog
            reply = QMessageBox.question(
                self,
                self.tr('Windows Defender'),
                self.tr(
                    'Do you want to exclude this application from Windows Defender scanning?\n\n'
                    'This requires administrator rights. A confirmation dialog (UAC) will appear.\n\n'
                    'Note: Excluding the program will speed up startup '
                    'but will reduce protection for that specific application.'
                ),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )

            if reply == QMessageBox.StandardButton.Yes:
                # Ausnahme hinzufügen
                success, message = add_defender_exclusion()

                if success:
                    # Erfolg
                    QMessageBox.information(
                        self,
                        self.tr('Windows Defender'),
                        message
                    )

                    # Settings aktualisieren
                    self.general_settings.defender_settings.exclusion_asked = True
                    general_settings_handler.save_to_toml_file(self.general_settings)

                    # Status neu laden
                    self._update_defender_status()
                else:
                    # Fehler
                    QMessageBox.warning(
                        self,
                        self.tr('Windows Defender'),
                        message
                    )

        except Exception as e:
            QMessageBox.critical(
                self,
                self.tr('Error'),
                self.tr('Error adding Defender exception:\n{exception}').format(exception=str(e))
            )

    def accept(self):
        self.general_settings.plan_settings.column_width_plan = self.spin_column_width.value()
        self.general_settings.plan_settings.column_width_statistics = self.spin_column_width_statistics.value()
        self.general_settings.language = self.combo_language.currentData()
        self.date_format_selector.save_settings()
        self.excel_folder_date_selector.save_settings()
        general_settings_handler.save_to_toml_file(self.general_settings)
        super().accept()
