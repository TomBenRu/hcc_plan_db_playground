"""
Hauptmodul der GUI-Integration für die E-Mail-Funktionalität.

Dieses Modul importiert alle benötigten Klassen aus den Teil-Modulen und
bietet einfache Funktionen zum Öffnen der verschiedenen Dialoge.
"""

import logging
from pathlib import Path
from uuid import UUID

from gui.email_to_users.gui_integration_bulk_email import BulkEmailDialog
from .gui_integration_email_config import EmailConfigDialog
from .gui_integration_plan_notification import PlanNotificationDialog
from .gui_integration_availability_request import AvailabilityRequestDialog
from .gui_integration_custom_email import CustomEmailDialog
from email_to_users.config import load_config_from_file


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


def show_plan_notification_dialog(parent=None):
    """
    Zeigt den Dialog zum Senden von Einsatzplan-Benachrichtigungen an.
    
    Args:
        parent: Übergeordnetes Widget
        
    Returns:
        bool: True, wenn die E-Mails gesendet wurden, sonst False
    """
    dialog = PlanNotificationDialog(parent)
    return dialog.exec() == 1


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


def show_custom_email_dialog(parent=None, project_id: UUID = None):
    """
    Zeigt den Dialog zum Senden von benutzerdefinierten E-Mails an.
    
    Args:
        parent: Übergeordnetes Widget
        project_id: Optional, ID des Projekts
        
    Returns:
        bool: True, wenn die E-Mails gesendet wurden, sonst False
    """
    dialog = CustomEmailDialog(parent, project_id)
    return dialog.exec() == 1


def show_bulk_email_dialog(parent=None, project_id: UUID = None):
    """
    Zeigt den Dialog zum Senden von Massen-E-Mails an.

    Args:
        parent: Übergeordnetes Widget
        project_id: Optional, ID des Projekts

    Returns:
        bool: True, wenn die E-Mails gesendet wurden, sonst False
    """
    dialog = BulkEmailDialog(parent, project_id)
    return dialog.exec() == 1


# Beim Import des Moduls die Konfiguration laden
load_email_config()


if __name__ == '__main__':
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    show_plan_notification_dialog()
    sys.exit(app.exec())
