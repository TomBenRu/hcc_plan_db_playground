"""
Custom Widgets Package für HCC Plan DB Playground

Erweiterte Qt-Widgets für spezielle Anwendungsfälle:
- WorkloadHeatDelegate: Heat-Map-Visualisierung für Auslastungsdarstellung
- BaseConfigButton: Basisklasse für Config-Buttons im AvailDay-Grid

Erstellt: 31. August 2025
Aktualisiert: Januar 2026 - BaseConfigButton hinzugefügt
"""

from gui.custom_widgets.base_config_button import BaseConfigButton

# WorkloadHeatDelegate temporär deaktiviert wegen Circular Import

__all__ = [
    "BaseConfigButton",
    # WorkloadHeatDelegate temporär deaktiviert wegen Circular Import
]

# Version für Feature-Tracking
__version__ = "1.1.0"
