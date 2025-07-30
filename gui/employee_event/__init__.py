"""
GUI Module für Employee Event Management.

Stellt alle UI-Komponenten für die Verwaltung von Employee Events bereit:
- Hauptfenster mit Listen- und Kalenderansicht
- Event-Details-Dialoge für CRUD-Operationen  
- Kategorie-Verwaltung
- Filter-System für Teams, Kategorien und Freitextsuche
"""

from .frm_employee_event_main import FrmEmployeeEventMain
from .dlg_employee_event_details import DlgEmployeeEventDetails

__all__ = [
    "FrmEmployeeEventMain",
    "DlgEmployeeEventDetails"
]
