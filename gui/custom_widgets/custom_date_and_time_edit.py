"""
Custom Date/Time Edit Widgets mit automatischer Locale-Konfiguration.

Bietet DateEditLocale und TimeEditLocale Widgets, die automatisch 
die System-Locale-Einstellungen anwenden.
"""

import logging
from typing import Optional

from PySide6.QtCore import QDate, QTime, QLocale
from PySide6.QtWidgets import QDateEdit, QTimeEdit, QCalendarWidget

from configuration.general_settings import general_settings_handler

logger = logging.getLogger(__name__)


class CalendarLocale(QCalendarWidget):
    """
    QCalendarWidget mit automatischer Locale-Konfiguration.

    Konfiguriert automatisch das Datumsformat und die Locale basierend
    auf den general_settings. Vereinfacht die Verwendung von QCalendarWidget
    in verschiedenen Teilen der Anwendung.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        try:
            # General Settings laden
            date_format_settings = general_settings_handler.get_general_settings().date_format_settings

            # QLocale erstellen
            locale = QLocale(
                QLocale.Language(date_format_settings.language),
                QLocale.Country(date_format_settings.country)
            )
            self.setLocale(locale)
        except Exception as e:
            logger.error(f"Error initializing CalendarLocale: {e}")


class DateEditLocale(QDateEdit):
    """
    QDateEdit mit automatischer Locale-Konfiguration.
    
    Konfiguriert automatisch das Datumsformat und die Locale basierend
    auf den general_settings. Vereinfacht die Verwendung von QDateEdit
    in verschiedenen Teilen der Anwendung.
    """
    
    def __init__(self, parent=None, date: Optional[QDate] = None, calendar_popup: bool = True):
        super().__init__(parent)
        
        try:
            # General Settings laden
            date_format_settings = general_settings_handler.get_general_settings().date_format_settings
            
            # QLocale erstellen
            locale = QLocale(
                QLocale.Language(date_format_settings.language),
                QLocale.Country(date_format_settings.country)
            )
            
            # Integer-Wert zu QLocale.FormatType konvertieren
            format_type = QLocale.FormatType(date_format_settings.format)
            
            # Das korrekte Datum-Format aus dem QLocale holen
            date_display_format = locale.dateFormat(format_type)
            
            # Widget konfigurieren
            self.setDisplayFormat(date_display_format)
            self.setLocale(locale)
            self.setCalendarPopup(calendar_popup)
            
            # Initial-Datum setzen
            if date:
                self.setDate(date)
            else:
                self.setDate(QDate.currentDate())
            
        except Exception as e:
            logger.error(f"Error initializing DateEditLocale: {e}")
            # Fallback-Konfiguration
            self.setDisplayFormat("dd.MM.yyyy")
            self.setCalendarPopup(True)
            self.setDate(QDate.currentDate())


class TimeEditLocale(QTimeEdit):
    """
    QTimeEdit mit konsistenter Konfiguration.
    
    Bietet eine einheitliche Zeit-Eingabe mit standardmäßiger 24h-Formatierung.
    Kann zukünftig erweitert werden um auch Zeit-Locale-Einstellungen zu unterstützen.
    """
    
    def __init__(self, parent=None, time: Optional[QTime] = None):
        super().__init__(parent)
        
        try:
            # Standard 24h-Format
            self.setDisplayFormat("hh:mm")

            
            # Initial-Zeit setzen
            if time:
                self.setTime(time)
            else:
                self.setTime(QTime.currentTime())
            
        except Exception as e:
            logger.error(f"Error initializing TimeEditLocale: {e}")
            # Fallback-Konfiguration
            self.setDisplayFormat("hh:mm")
            self.setTime(QTime.currentTime())


class DateTimeEditLocale:
    """
    Helper-Klasse zum Erstellen von Datum/Zeit-Eingabe-Paaren.
    
    Erstellt automatisch ein DateEditLocale und TimeEditLocale mit
    konsistenter Konfiguration.
    """
    
    def __init__(self, parent=None, date: Optional[QDate] = None, time: Optional[QTime] = None):
        """
        Erstellt ein Datum/Zeit-Eingabe-Paar.
        
        Args:
            parent: Parent Widget
            date: Initial-Datum (default: heute)
            time: Initial-Zeit (default: aktuelle Zeit)
        """
        self.date_edit = DateEditLocale(parent, date)
        self.time_edit = TimeEditLocale(parent, time)
    
    def get_date_edit(self) -> DateEditLocale:
        """Gibt das DateEdit Widget zurück."""
        return self.date_edit
    
    def get_time_edit(self) -> TimeEditLocale:
        """Gibt das TimeEdit Widget zurück."""
        return self.time_edit
    
    def set_minimum_date_time(self, date: QDate, time: QTime):
        """Setzt Minimum-Datum und -Zeit für beide Widgets."""
        self.date_edit.setMinimumDate(date)
        # Für Time-Minimum muss das Datum verglichen werden
        if self.date_edit.date() == date:
            self.time_edit.setMinimumTime(time)
        else:
            self.time_edit.setMinimumTime(QTime(0, 0))
