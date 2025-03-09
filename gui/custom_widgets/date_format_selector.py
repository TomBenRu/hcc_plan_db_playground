from PySide6.QtCore import QLocale, QDate
from PySide6.QtWidgets import QWidget, QComboBox, QFormLayout, QLabel, QApplication

from configuration.general_settings import general_settings_handler
from gui.custom_widgets.qcombobox_find_data import QComboBoxToFindData


class LocaleSelector(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Locale Selector")

        self.general_settings = general_settings_handler.get_general_settings()
        self.date_format_settings = self.general_settings.date_format_settings

        # Layout erstellen
        layout = QFormLayout(self)

        # ComboBoxes erstellen
        self.combo_country = QComboBoxToFindData()
        self.combo_language = QComboBoxToFindData()
        self.combo_format = QComboBoxToFindData()
        self.label_date = QLabel()

        # Widgets zum Layout hinzufügen
        layout.addRow("Country:", self.combo_country)
        layout.addRow("Language:", self.combo_language)
        layout.addRow("Date Format:", self.combo_format)
        layout.addRow("Current Date:", self.label_date)

        # Länder zur Länder-ComboBox hinzufügen
        all_territories = {
            l.territory() for l in QLocale.matchingLocales(QLocale.Language.AnyLanguage,
                                                           QLocale.Script.AnyScript,
                                                           QLocale.Country.AnyCountry)
        }
        for territory in sorted(all_territories, key=lambda x: x.name):
            self.combo_country.addItem(territory.name, territory)

        # Datumsformate zur Format-ComboBox hinzufügen
        self.date_formats = {
            self.tr("Full Date"): QLocale.FormatType.LongFormat,  # z.B. "Sonntag, 9. März 2025"
            self.tr("Long Format"): QLocale.FormatType.ShortFormat,  # z.B. "09.03.2025"
            self.tr("Narrow Format"): QLocale.FormatType.NarrowFormat  # z.B. "09.03.25"
        }
        for format_name, format_type in self.date_formats.items():
            self.combo_format.addItem(format_name, format_type)

        # Initial die Länder für die erste Sprache laden
        self.update_language(self.combo_language.currentText())

        # Initial das Datum anzeigen
        self.update_date_format()

        # Signale verbinden
        self.combo_country.currentIndexChanged.connect(self.update_date_format)
        self.combo_country.currentIndexChanged.connect(self.update_language)
        self.combo_language.currentIndexChanged.connect(self.update_date_format)
        self.combo_format.currentTextChanged.connect(self.update_date_format)

        # Initialer Zustand laden
        self.load_initial_state()

    def closeEvent(self, event, /):
        self.save_settings()
        super().closeEvent(event)

    def save_settings(self):
        self.date_format_settings.country = self.combo_country.currentData().value
        self.date_format_settings.language = self.combo_language.currentData().value
        self.date_format_settings.format = self.combo_format.currentData().value
        general_settings_handler.save_to_toml_file(self.general_settings)

    def load_initial_state(self):
        curr_country, curr_language, curr_format = (QLocale.Country(self.date_format_settings.country),
                                                    QLocale.Language(self.date_format_settings.language),
                                                    QLocale.FormatType(self.date_format_settings.format))
        self.combo_country.setCurrentIndex(self.combo_country.findData(curr_country))
        self.combo_language.setCurrentIndex(self.combo_language.findData(curr_language))
        self.combo_format.setCurrentIndex(self.combo_format.findData(curr_format))

    def update_language(self, country_index):
        # ComboBox für Sprachen leeren
        self.combo_language.clear()

        languages = {l.language() for l in QLocale.matchingLocales(QLocale.Language.AnyLanguage,
                                                                   QLocale.Script.AnyScript,
                                                                   self.combo_country.currentData())
                     if not l.language().name in ('AnyLanguage', 'C')}

        # Sprachen für das ausgewählte Land laden
        for language in sorted(languages, key=lambda x: x.name):
            self.combo_language.addItem(language.name, language)

        # Nach dem Aktualisieren der Länder das Datum neu formatieren
        self.update_date_format()

    def update_date_format(self):
        locale = self.get_selected_locale()
        current_date = QDate.currentDate()
        format_type = self.combo_format.currentData()

        if self.combo_format.currentData() == QLocale.FormatType.ShortFormat:
            # Eventuelle 2-stellige Jahreszahl soll in 4-stellige Jahreszahl umgewandelt werden.
            # Die länderspezifische Formatierung soll aber erhalten bleiben.

            # Zuerst das Datum im Kurzformat holen
            formatted_date = locale.toString(current_date, format_type)

            # Das Jahr im 4-stelligen Format bekommen
            full_year = str(current_date.year())

            if full_year not in formatted_date:
                # Die letzten zwei Ziffern des Jahres finden und durch das vollständige Jahr ersetzen
                short_year = str(current_date.year() % 100).zfill(2)
                formatted_date = formatted_date.replace(short_year, full_year)
        else:
            # Normale Formatierung für andere Formate
            formatted_date = locale.toString(current_date, format_type)

        self.label_date.setText(f"{formatted_date}")

    def get_selected_locale(self) -> QLocale:
        """Gibt die aktuell ausgewählte Locale zurück"""
        language = self.combo_language.currentText()
        country = self.combo_country.currentText()

        # Finde die entsprechende Locale
        for locale in QLocale.matchingLocales(QLocale.Language.AnyLanguage,
                                              QLocale.Script.AnyScript,
                                              QLocale.Country.AnyCountry):
            if (QLocale.languageToString(locale.language()) == language and
                    locale.territory().name == country):
                return locale

        return QLocale()  # Fallback auf System-Locale


if __name__ == '__main__':
    app = QApplication([])
    window = LocaleSelector()
    window.show()
    app.exec()