"""
Hilfsfunktionen zur Formatierung von Datumsangaben für Excel-Ordnernamen.

Diese Funktionen verwenden die konfigurierbaren Einstellungen aus den
GeneralSettings, um Datumsbereiche konsistent zu formatieren.
"""

import datetime

from configuration.general_settings import general_settings_handler, ExcelFolderDateFormatSettings


def format_excel_folder_date(date: datetime.date,
                             settings: ExcelFolderDateFormatSettings | None = None) -> str:
    """
    Formatiert ein Datum gemäß den Excel-Ordner-Einstellungen.

    Args:
        date: Das zu formatierende Datum
        settings: Optionale Einstellungen. Falls None, werden die
                  gespeicherten Einstellungen verwendet.

    Returns:
        Das formatierte Datum als String (z.B. "01.12.24")
    """
    if settings is None:
        settings = general_settings_handler.get_general_settings().excel_folder_date_format

    # Komponenten formatieren
    day = date.strftime(settings.day_format)
    month = date.strftime(settings.month_format)
    year = date.strftime(settings.year_format)

    # Reihenfolge anwenden
    order_map = {
        'dmy': [day, month, year],
        'mdy': [month, day, year],
        'ymd': [year, month, day],
    }
    components = order_map.get(settings.order, order_map['dmy'])

    return settings.component_separator.join(components)


def format_excel_folder_date_range(start: datetime.date,
                                   end: datetime.date,
                                   settings: ExcelFolderDateFormatSettings | None = None) -> str:
    """
    Formatiert einen Datumsbereich für Excel-Ordnernamen.

    Args:
        start: Startdatum des Bereichs
        end: Enddatum des Bereichs
        settings: Optionale Einstellungen. Falls None, werden die
                  gespeicherten Einstellungen verwendet.

    Returns:
        Der formatierte Datumsbereich als String (z.B. "01.12.24-31.12.24")
    """
    if settings is None:
        settings = general_settings_handler.get_general_settings().excel_folder_date_format

    start_str = format_excel_folder_date(start, settings)
    end_str = format_excel_folder_date(end, settings)

    return f"{start_str}{settings.date_separator}{end_str}"
