"""
Custom Date/Time Edit Widgets mit automatischer Locale-Konfiguration.

Bietet DateEditLocale und TimeEditLocale Widgets, die automatisch 
die System-Locale-Einstellungen anwenden.
"""
import datetime
import logging
from typing import Optional

from PySide6.QtCore import QDate, QTime, QLocale, QRect
from PySide6.QtGui import QColor, QBrush, QPen, QFont, QPainter
from PySide6.QtWidgets import QDateEdit, QTimeEdit, QCalendarWidget

from configuration.general_settings import general_settings_handler
from employee_event import EventDetail

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



class HighlightCalendarLocale(CalendarLocale):
    """
    CalendarLocale mit erweiterten Hervorhebungs-Funktionen für Events.
    
    Zeigt Event-Tage mit visuellen Indikatoren an und kann 
    unterschiedliche Event-Typen farblich unterscheiden.
    
    Features:
    - Kleine Indikatoren für Event-Tage
    - Event-Anzahl-Anzeige bei mehreren Events
    - Kategorie-spezifische Farben (optional)
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.event_dates: dict[datetime.date, list[EventDetail]] = {}  # date -> [events]
        
        # Farben für Event-Indikatoren
        self.primary_indicator_color = "#466d00"    # Hauptfarbe (Akzent)
        self.secondary_indicator_color = "#385700"  # Sekundärfarbe
        self.multi_event_color = "#ffaa00"          # Farbe für mehrere Events
        self.indicator_size = 12
        self.indicator_margin = 6
    
    def set_event_dates(self, events: list[EventDetail]):
        """
        Setzt die Events für die Hervorhebung im Kalender.
        
        Args:
            events: Liste von EventDetail-Objekten
        """
        import datetime
        
        self.event_dates.clear()
        
        for event_detail in events:
            start_date = event_detail.start.date()
            end_date = event_detail.end.date()
            
            # Alle Tage zwischen Start und Ende markieren (mehrtägige Events)
            current_date = start_date
            while current_date <= end_date:
                if current_date not in self.event_dates:
                    self.event_dates[current_date] = []
                self.event_dates[current_date].append(event_detail)
                current_date = current_date + datetime.timedelta(days=1)
        
        # Kalender neu zeichnen
        self.update()
        
        logger.debug(f"HighlightCalendarLocale: Hervorhebung für {len(self.event_dates)} Event-Tage gesetzt")
    
    def clear_event_dates(self):
        """Entfernt alle Event-Hervorhebungen."""
        self.event_dates.clear()
        self.update()
    
    def paintCell(self, painter, rect, date):
        """
        Überschreibt das Zeichnen der Kalenderzellen für Event-Hervorhebung.
        
        Args:
            painter: QPainter für das Zeichnen
            rect: QRect der Zelle
            date: QDate der Zelle
        """
        # Standard-Zeichnung der Zelle
        super().paintCell(painter, rect, date)
        
        # Event-Daten für dieses Datum prüfen
        python_date = date.toPython()
        if python_date not in self.event_dates:
            return
        
        events_for_date = self.event_dates[python_date]
        event_count = len(events_for_date)
        
        # Event-Indikatoren zeichnen
        self._draw_event_indicators(painter, rect, event_count)
        
        # Event-Anzahl anzeigen (bei mehr als einem Event)
        if event_count > 1:
            self._draw_event_count(painter, rect, event_count)
    
    def _draw_event_indicators(self, painter: QPainter, rect: QRect, event_count: int):
        """
        Zeichnet visuelle Indikatoren für Events in der Kalenderzelle.
        
        Args:
            painter: QPainter für das Zeichnen
            rect: QRect der Zelle
            event_count: Anzahl der Events
        """
        from PySide6.QtGui import QColor, QBrush, QPen
        from PySide6.QtCore import Qt
        
        # Position für Indikator (rechts, vertikal zentriert)
        indicator_x = rect.right() - self.indicator_size - self.indicator_margin
        indicator_y = rect.bottom() - self.indicator_size - self.indicator_margin
        
        # Farbe basierend auf Event-Anzahl
        if event_count == 1:
            color = QColor(self.primary_indicator_color)
        else:
            color = QColor(self.multi_event_color)
        
        # Indikator zeichnen
        painter.save()
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(self.secondary_indicator_color), 2))
        painter.drawEllipse(indicator_x, indicator_y, self.indicator_size, self.indicator_size)
        painter.restore()
    
    def _draw_event_count(self, painter: QPainter, rect: QRect, event_count: int):
        """
        Zeichnet die Event-Anzahl in die Kalenderzelle.
        
        Args:
            painter: QPainter für das Zeichnen
            rect: QRect der Zelle
            event_count: Anzahl der Events
        """
        from PySide6.QtGui import QColor, QFont
        from PySide6.QtCore import Qt
        
        # Nur bei mehr als einem Event anzeigen
        if event_count <= 1:
            return
        
        painter.save()
        
        # Schrift für Event-Anzahl
        font = painter.font()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        
        # Farbe für Text
        painter.setPen(QColor("white"))
        
        # Event-Anzahl positionieren (links oben)
        text_rect = rect.adjusted(self.indicator_margin, self.indicator_margin, -2, -2)
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, str(event_count))
        
        painter.restore()
    
    def get_events_for_date(self, date: QDate | datetime.date) -> list[EventDetail]:
        """
        Gibt die Events für ein bestimmtes Datum zurück.
        
        Args:
            date: QDate oder Python date
            
        Returns:
            List[EventDetail]: Liste der Events für das Datum
        """
        if hasattr(date, 'toPython'):
            python_date = date.toPython()
        else:
            python_date = date
            
        return self.event_dates.get(python_date, [])


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
