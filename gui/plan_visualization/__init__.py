"""
Plan Visualization Package für HCC Plan DB Playground

Enthält alle Visualisierungs-Komponenten für erweiterte Plandarstellung:
- WorkloadCalculator: Auslastungsberechnungen für Heat-Maps  
- WorkloadCache: Performance-Optimierung mit intelligentem Caching
- WorkloadHeatDelegate: Custom Qt-Delegate für farbige Darstellung
- Model-Integration: Flexible Integration in bestehende Qt-Models
- HeatMapController: Einfache Integration in bestehende Views

Erstellt: 31. August 2025
"""

from .workload_calculator import WorkloadCalculator, WorkloadCache
# Weitere Komponenten temporär deaktiviert wegen Circular Import Issues
# from .workload_model_integration import WorkloadDataProvider, WorkloadModelMixin, add_workload_support_to_model  
# from .heat_map_integration import HeatMapController, HeatMapControlWidget, create_heat_map_integration

__all__ = [
    'WorkloadCalculator',
    'WorkloadCache',
    # Weitere Komponenten temporär deaktiviert
]

# Version für Feature-Tracking
__version__ = "1.0.0"
