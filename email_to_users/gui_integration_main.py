"""
Hauptmodul der GUI-Integration für die E-Mail-Funktionalität.

Dieses Modul importiert alle benötigten Klassen aus den Teil-Modulen und
bietet einfache Funktionen zum Öffnen der verschiedenen Dialoge.
"""

import os
import logging
from pathlib import Path
from pony.orm import db_session

try:
    # Importiere die Dialoge der einzelnen Teile
    from .gui_integration import EmailConfigDialog
    from .gui_integration_part2 import PlanNotificationDialog
    from .gui_integration_part3 import AvailabilityRequestDialog
    from .gui_integration_part4 import CustomEmailDialog
    from .config import load_config_from_file
    
except ImportError:
    # Falls die Dateien direkt als Module ausgeführt werden
    from gui_integration import EmailConfigDialog
    from gui_integration_part2 import PlanNotificationDialog
    from gui_integration_part3 import AvailabilityRequestDialog
    from gui_integration_part4 import CustomEmailDialog
    from config import load_config_from_file

logger = logging.getLogger(__name__)


def load_email_config():
    """
    Lädt die E-Mail-Konfiguration aus der Konfigurationsdatei.
    
    Returns:
        bool: True, wenn die Konfiguration geladen wurde, sonst False
    """
    config_path = Path("configuration") / "email_config.toml"
    if config_path.exists():
        try:
            load_config_from_file(str(config_path))
            return True
        except Exception as e:
            logger.error(f"Fehler beim Laden der E-Mail-Konfiguration: {str(e)}")
            return False
    return False


def show_config_dialog(parent=None):
    """
    Zeigt den Dialog zur Konfiguration der E-Mail-Einstellungen an.
    
    Args:
        parent: Übergeordnetes Widget
        
    Returns:
        bool: True, wenn die Konfiguration gespeichert wurde, sonst False
    """
    dialog = EmailConfigDialog(parent)
    return dialog.exec_() == 1


def show_plan_notification_dialog(plan_id, parent=None):
    """
    Zeigt den Dialog zum Senden von Einsatzplan-Benachrichtigungen an.
    
    Args:
        plan_id: ID des Plans
        parent: Übergeordnetes Widget
        
    Returns:
        bool: True, wenn die E-Mails gesendet wurden, sonst False
    """
    dialog = PlanNotificationDialog(plan_id, parent)
    return dialog.exec_() == 1


def show_availability_request_dialog(plan_period_id, parent=None):
    """
    Zeigt den Dialog zum Senden von Verfügbarkeitsanfragen an.
    
    Args:
        plan_period_id: ID des Planungszeitraums
        parent: Übergeordnetes Widget
        
    Returns:
        bool: True, wenn die E-Mails gesendet wurden, sonst False
    """
    dialog = AvailabilityRequestDialog(plan_period_id, parent)
    return dialog.exec_() == 1


def show_custom_email_dialog(parent=None):
    """
    Zeigt den Dialog zum Senden von benutzerdefinierten E-Mails an.
    
    Args:
        parent: Übergeordnetes Widget
        
    Returns:
        bool: True, wenn die E-Mails gesendet wurden, sonst False
    """
    dialog = CustomEmailDialog(parent)
    return dialog.exec_() == 1


# Beim Import des Moduls die Konfiguration laden
load_email_config()


if __name__ == '__main__':
    show_custom_email_dialog()
