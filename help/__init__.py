"""
HCC Plan Help System - Vereinfachte Browser-Only Version

Einfaches Hilfe-System das HTML-Dateien direkt im Browser öffnet.
Keine Kompilierung oder Qt Assistant erforderlich.

Autor: HCC Plan Development Team
Version: 2.0.0 (Vereinfacht)
"""

from .help_manager import HelpManager
from .help_integration import HelpIntegration

__version__ = "2.0.0"
__all__ = ["HelpManager", "HelpIntegration", "init_help_system", "get_help_manager"]

# Globaler Help Manager
_help_manager = None


def init_help_system(app=None, project_root=None) -> HelpManager:
    """
    Initialisiert das Hilfe-System.
    
    Args:
        app: QApplication Instanz (für Kompatibilität, wird ignoriert)
        project_root: Pfad zum Projekt-Root (optional)
        
    Returns:
        HelpManager: Der initialisierte Help Manager
    """
    global _help_manager
    
    if _help_manager is None:
        _help_manager = HelpManager(project_root)
    
    return _help_manager


def get_help_manager() -> HelpManager:
    """
    Gibt den aktuellen Help Manager zurück.
    
    Returns:
        HelpManager: Der Help Manager oder None wenn nicht initialisiert
    """
    return _help_manager
