import datetime
import platform

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QFormLayout, QComboBox,
                               QLineEdit, QLabel, QHBoxLayout, QFrame)

from configuration.general_settings import general_settings_handler, ExcelFolderDateFormatSettings


class ExcelFolderDateFormatSelector(QWidget):
    """
    Widget zur Konfiguration des Datumsformats für Excel-Export-Ordnernamen.

    Ermöglicht die flexible Anordnung von Tag, Monat und Jahr sowie
    individuelle Trennzeichen.
    """

    settings_changed = Signal()

    # Presets: (name, day_format, month_format, year_format, order, component_sep, date_sep)
    PRESETS = {
        'german_short': ('%d', '%m', '%y', 'dmy', '.', '-'),
        'german_long': ('%d', '%m', '%Y', 'dmy', '.', '-'),
        'iso8601': ('%d', '%m', '%Y', 'ymd', '-', '_'),
        'us_short': ('%d', '%m', '%y', 'mdy', '/', '-'),
        'us_long': ('%d', '%m', '%Y', 'mdy', '/', '-'),
    }

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setContentsMargins(0, 0, 0, 0)

        self._updating_from_preset = False

        self.general_settings = general_settings_handler.get_general_settings()
        self.excel_folder_settings = self.general_settings.excel_folder_date_format

        self._setup_ui()
        self._setup_connections()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        form_layout = QFormLayout()
        form_layout.setContentsMargins(0, 0, 0, 0)

        # Reihenfolge
        self.combo_order = QComboBox()
        self.combo_order.addItem(self.tr('Day - Month - Year'), 'dmy')
        self.combo_order.addItem(self.tr('Month - Day - Year'), 'mdy')
        self.combo_order.addItem(self.tr('Year - Month - Day'), 'ymd')
        form_layout.addRow(self.tr('Order:'), self.combo_order)

        # Tag-Format
        self.combo_day_format = QComboBox()
        self._populate_day_formats()
        form_layout.addRow(self.tr('Day format:'), self.combo_day_format)

        # Monat-Format
        self.combo_month_format = QComboBox()
        self._populate_month_formats()
        form_layout.addRow(self.tr('Month format:'), self.combo_month_format)

        # Jahr-Format
        self.combo_year_format = QComboBox()
        self.combo_year_format.addItem(self.tr('Two digits (24)'), '%y')
        self.combo_year_format.addItem(self.tr('Four digits (2024)'), '%Y')
        form_layout.addRow(self.tr('Year format:'), self.combo_year_format)

        # Trennzeichen für Datumskomponenten
        self.line_component_separator = QLineEdit()
        self.line_component_separator.setMaxLength(3)
        self.line_component_separator.setMaximumWidth(50)
        form_layout.addRow(self.tr('Date separator:'), self.line_component_separator)

        # Trennzeichen für Datumsbereich
        self.line_date_separator = QLineEdit()
        self.line_date_separator.setMaxLength(5)
        self.line_date_separator.setMaximumWidth(50)
        form_layout.addRow(self.tr('Range separator:'), self.line_date_separator)

        layout.addLayout(form_layout)

        # Trennlinie
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)

        # Presets
        preset_layout = QFormLayout()
        preset_layout.setContentsMargins(0, 5, 0, 0)
        self.combo_presets = QComboBox()
        self.combo_presets.addItem(self.tr('Custom'), 'custom')
        self.combo_presets.addItem(self.tr('German (DD.MM.YY)'), 'german_short')
        self.combo_presets.addItem(self.tr('German long (DD.MM.YYYY)'), 'german_long')
        self.combo_presets.addItem(self.tr('ISO 8601 (YYYY-MM-DD)'), 'iso8601')
        self.combo_presets.addItem(self.tr('US Format (MM/DD/YY)'), 'us_short')
        self.combo_presets.addItem(self.tr('US Format long (MM/DD/YYYY)'), 'us_long')
        preset_layout.addRow(self.tr('Presets:'), self.combo_presets)
        layout.addLayout(preset_layout)

        # Vorschau
        preview_layout = QHBoxLayout()
        preview_layout.setContentsMargins(0, 10, 0, 0)
        preview_label = QLabel(self.tr('Preview:'))
        self.label_preview = QLabel()
        self.label_preview.setStyleSheet('font-weight: bold; padding: 5px; '
                                         'background-color: palette(base); '
                                         'border: 1px solid palette(mid); '
                                         'border-radius: 3px;')
        preview_layout.addWidget(preview_label)
        preview_layout.addWidget(self.label_preview)
        preview_layout.addStretch()
        layout.addLayout(preview_layout)

    def _populate_day_formats(self):
        """Füllt die Tag-Format ComboBox."""
        self.combo_day_format.addItem(self.tr('With leading zero (01)'), '%d')
        # Plattformspezifisch: Windows verwendet %#d, Unix verwendet %-d
        no_leading_zero = '%#d' if platform.system() == 'Windows' else '%-d'
        self.combo_day_format.addItem(self.tr('Without leading zero (1)'), no_leading_zero)

    def _populate_month_formats(self):
        """Füllt die Monat-Format ComboBox."""
        self.combo_month_format.addItem(self.tr('With leading zero (01)'), '%m')
        no_leading_zero = '%#m' if platform.system() == 'Windows' else '%-m'
        self.combo_month_format.addItem(self.tr('Without leading zero (1)'), no_leading_zero)
        self.combo_month_format.addItem(self.tr('Abbreviated (Jan)'), '%b')
        self.combo_month_format.addItem(self.tr('Full name (January)'), '%B')

    def _setup_connections(self):
        """Verbindet Signale mit Slots."""
        # Alle Änderungen aktualisieren die Vorschau und setzen Preset auf "Custom"
        self.combo_order.currentIndexChanged.connect(self._on_setting_changed)
        self.combo_day_format.currentIndexChanged.connect(self._on_setting_changed)
        self.combo_month_format.currentIndexChanged.connect(self._on_setting_changed)
        self.combo_year_format.currentIndexChanged.connect(self._on_setting_changed)
        self.line_component_separator.textChanged.connect(self._on_setting_changed)
        self.line_date_separator.textChanged.connect(self._on_setting_changed)

        # Preset-Auswahl
        self.combo_presets.currentIndexChanged.connect(self._on_preset_changed)

    def _load_settings(self):
        """Lädt die gespeicherten Einstellungen in die UI."""
        settings = self.excel_folder_settings

        # Reihenfolge
        index = self.combo_order.findData(settings.order)
        if index >= 0:
            self.combo_order.setCurrentIndex(index)

        # Tag-Format
        index = self.combo_day_format.findData(settings.day_format)
        if index >= 0:
            self.combo_day_format.setCurrentIndex(index)

        # Monat-Format
        index = self.combo_month_format.findData(settings.month_format)
        if index >= 0:
            self.combo_month_format.setCurrentIndex(index)

        # Jahr-Format
        index = self.combo_year_format.findData(settings.year_format)
        if index >= 0:
            self.combo_year_format.setCurrentIndex(index)

        # Trennzeichen
        self.line_component_separator.setText(settings.component_separator)
        self.line_date_separator.setText(settings.date_separator)

        # Preset ermitteln
        self._update_preset_selection()
        self._update_preview()

    def save_settings(self):
        """Speichert die aktuellen Einstellungen."""
        self.excel_folder_settings.order = self.combo_order.currentData()
        self.excel_folder_settings.day_format = self.combo_day_format.currentData()
        self.excel_folder_settings.month_format = self.combo_month_format.currentData()
        self.excel_folder_settings.year_format = self.combo_year_format.currentData()
        self.excel_folder_settings.component_separator = self.line_component_separator.text()
        self.excel_folder_settings.date_separator = self.line_date_separator.text()

        general_settings_handler.save_to_toml_file(self.general_settings)

    def _on_setting_changed(self):
        """Wird aufgerufen, wenn eine Einstellung geändert wird."""
        if not self._updating_from_preset:
            self._update_preset_selection()
        self._update_preview()
        self.settings_changed.emit()

    def _on_preset_changed(self, index: int):
        """Wird aufgerufen, wenn ein Preset ausgewählt wird."""
        preset_key = self.combo_presets.currentData()
        if preset_key and preset_key != 'custom':
            self._apply_preset(preset_key)

    def _apply_preset(self, preset_key: str):
        """Wendet ein Preset auf die Einstellungen an."""
        if preset_key not in self.PRESETS:
            return

        self._updating_from_preset = True

        day_fmt, month_fmt, year_fmt, order, comp_sep, date_sep = self.PRESETS[preset_key]

        # Reihenfolge setzen
        index = self.combo_order.findData(order)
        if index >= 0:
            self.combo_order.setCurrentIndex(index)

        # Tag-Format: Preset verwendet immer %d, auf plattformspezifisch mappen falls nötig
        index = self.combo_day_format.findData(day_fmt)
        if index >= 0:
            self.combo_day_format.setCurrentIndex(index)

        # Monat-Format
        index = self.combo_month_format.findData(month_fmt)
        if index >= 0:
            self.combo_month_format.setCurrentIndex(index)

        # Jahr-Format
        index = self.combo_year_format.findData(year_fmt)
        if index >= 0:
            self.combo_year_format.setCurrentIndex(index)

        # Trennzeichen
        self.line_component_separator.setText(comp_sep)
        self.line_date_separator.setText(date_sep)

        self._updating_from_preset = False
        self._update_preview()

    def _update_preset_selection(self):
        """Aktualisiert die Preset-Auswahl basierend auf den aktuellen Einstellungen."""
        current = (
            self.combo_day_format.currentData(),
            self.combo_month_format.currentData(),
            self.combo_year_format.currentData(),
            self.combo_order.currentData(),
            self.line_component_separator.text(),
            self.line_date_separator.text()
        )

        matched_preset = 'custom'
        for preset_key, preset_values in self.PRESETS.items():
            if current == preset_values:
                matched_preset = preset_key
                break

        # Preset-ComboBox aktualisieren ohne Signal auszulösen
        self.combo_presets.blockSignals(True)
        index = self.combo_presets.findData(matched_preset)
        if index >= 0:
            self.combo_presets.setCurrentIndex(index)
        self.combo_presets.blockSignals(False)

    def _update_preview(self):
        """Aktualisiert die Vorschau-Anzeige."""
        # Beispieldaten für die Vorschau
        start_date = datetime.date(2024, 12, 1)
        end_date = datetime.date(2024, 12, 31)

        preview_text = self.format_date_range(start_date, end_date)
        self.label_preview.setText(f'\U0001F4C1 {preview_text}')

    def format_date(self, date: datetime.date) -> str:
        """Formatiert ein einzelnes Datum gemäß den aktuellen Einstellungen."""
        day_fmt = self.combo_day_format.currentData()
        month_fmt = self.combo_month_format.currentData()
        year_fmt = self.combo_year_format.currentData()
        order = self.combo_order.currentData()
        separator = self.line_component_separator.text()

        # Komponenten formatieren
        day = date.strftime(day_fmt)
        month = date.strftime(month_fmt)
        year = date.strftime(year_fmt)

        # Reihenfolge anwenden
        order_map = {
            'dmy': [day, month, year],
            'mdy': [month, day, year],
            'ymd': [year, month, day],
        }
        components = order_map.get(order, order_map['dmy'])

        return separator.join(components)

    def format_date_range(self, start: datetime.date, end: datetime.date) -> str:
        """Formatiert einen Datumsbereich gemäß den aktuellen Einstellungen."""
        date_separator = self.line_date_separator.text()
        start_str = self.format_date(start)
        end_str = self.format_date(end)
        return f'{start_str}{date_separator}{end_str}'

    def get_current_settings(self) -> ExcelFolderDateFormatSettings:
        """Gibt die aktuellen Einstellungen als Objekt zurück."""
        return ExcelFolderDateFormatSettings(
            day_format=self.combo_day_format.currentData(),
            month_format=self.combo_month_format.currentData(),
            year_format=self.combo_year_format.currentData(),
            order=self.combo_order.currentData(),
            component_separator=self.line_component_separator.text(),
            date_separator=self.line_date_separator.text()
        )
