import os

import toml
from toml.decoder import TomlDecodeError

from pydantic import BaseModel

from configuration.config_handler import ConfigHandler
from configuration.project_paths import curr_user_path_handler


# QLocale-basierte Defaults nur auf Desktop verfuegbar. Auf Headless-Server
# (Web-API ohne PySide6) Fallback-Konstanten — der Server liest die echten
# Werte aus user-toml, GUI ueberschreibt Defaults beim ersten Speichern.
try:
    from PySide6.QtCore import QLocale
    _DEFAULT_COUNTRY = QLocale.Country.UnitedStates.value
    _DEFAULT_LANGUAGE = QLocale.Language.English.value
    _DEFAULT_FORMAT = QLocale.FormatType.ShortFormat.value
except ImportError:
    _DEFAULT_COUNTRY = 0
    _DEFAULT_LANGUAGE = 0
    _DEFAULT_FORMAT = 0


class PlanSettings(BaseModel):
    """
    Plan settings for the application.
    """
    column_width_plan: int = 120
    column_width_statistics: int = 100


class DateFormatSettings(BaseModel):
    """
    Date format settings for the application.
    """
    country: int = _DEFAULT_COUNTRY
    language: int = _DEFAULT_LANGUAGE
    format: int = _DEFAULT_FORMAT


class DefenderSettings(BaseModel):
    """
    Windows Defender exclusion settings.
    Speichert, ob der User bereits nach der Defender-Ausnahme gefragt wurde.
    """
    exclusion_asked: bool = False


class ExcelFolderDateFormatSettings(BaseModel):
    """
    Einstellungen für das Datumsformat im Excel-Ordnernamen.

    Attribute:
        day_format: Format für den Tag (%d = 01, %-d/%-#d = 1)
        month_format: Format für den Monat (%m = 01, %-m = 1, %b = Jan, %B = Januar)
        year_format: Format für das Jahr (%y = 24, %Y = 2024)
        order: Reihenfolge der Komponenten (dmy, mdy, ymd)
        component_separator: Trennzeichen zwischen Tag, Monat, Jahr (z.B. ".")
        date_separator: Trennzeichen zwischen Start- und Enddatum (z.B. "-")
    """
    day_format: str = "%d"
    month_format: str = "%m"
    year_format: str = "%y"
    order: str = "dmy"
    component_separator: str = "."
    date_separator: str = "-"


class GeneralSettings(BaseModel):
    """
    General settings for the application.
    """
    plan_settings: PlanSettings = PlanSettings()
    language: str = ''
    date_format_settings: DateFormatSettings = DateFormatSettings()
    defender_settings: DefenderSettings = DefenderSettings()
    excel_folder_date_format: ExcelFolderDateFormatSettings = ExcelFolderDateFormatSettings()


class GeneralSettingsHandler:
    """
    Handler for general settings.
    """
    def __init__(self):
        self._toml_dir = os.path.join(curr_user_path_handler.get_config().config_file_path, 'general_settings')
        self._toml_file = os.path.join(self._toml_dir, 'general_settings.toml')
        self._general_settings: GeneralSettings | None = None
        self.check_toml_dir()

    def check_toml_dir(self):
        if not os.path.exists(self._toml_dir):
            os.makedirs(self._toml_dir)

    def load_toml_file(self):
        try:
            with open(self._toml_file, 'r') as f:
                return GeneralSettings.model_validate(toml.load(f))
        except FileNotFoundError:
            return GeneralSettings()
        except TomlDecodeError:
            return GeneralSettings()

    def save_to_toml_file(self, general_settings: GeneralSettings):
        self._general_settings = general_settings
        with open(self._toml_file, 'w') as f:
            toml.dump(general_settings.model_dump(mode='json'), f)

    def get_general_settings(self) -> GeneralSettings:
        if self._general_settings is None:
            self._general_settings = self.load_toml_file()
        return self._general_settings


general_settings_handler = GeneralSettingsHandler()
