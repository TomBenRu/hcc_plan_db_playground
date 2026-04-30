"""
Paket für den E-Mail-Versand an Benutzer im HCC Plan DB Playground-Projekt.

Dieses Paket enthält Module für die Konfiguration, den E-Mail-Versand, Templates
und eine Service-Schicht für die Integration mit dem Datenmodell.
"""

# `email_config` und `email_service` bewusst NICHT eager re-exportieren —
# würde Lazy-Init in den Submodulen beim Package-Import triggern.
# Stattdessen über Module-Level __getattr__ (PEP 562) lazy bereitstellen.
from .config import EmailConfig, load_config_from_file
from .sender import EmailSender
from .service import EmailService, get_email_service
from .templates import EmailTemplate, PlanNotificationTemplate, AvailabilityRequestTemplate


def __getattr__(name: str):
    """Lazy-Provider für `email_service` und `email_config` als Package-Attribute."""
    if name == "email_service":
        return get_email_service()
    if name == "email_config":
        from .config import get_email_config
        return get_email_config()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


# GUI-Integration (nur importieren, wenn PySide6 verfügbar ist)
try:
    from gui.email_to_users.gui_integration_main import (
        show_config_dialog,
        show_plan_notification_dialog,
        show_availability_request_dialog,
        show_custom_email_dialog
    )
    __all__ = [
        'EmailConfig',
        'email_config',
        'load_config_from_file',
        'EmailSender',
        'EmailService',
        'email_service',
        'EmailTemplate',
        'PlanNotificationTemplate',
        'AvailabilityRequestTemplate',
        # GUI Funktionen
        'show_config_dialog',
        'show_plan_notification_dialog',
        'show_availability_request_dialog',
        'show_custom_email_dialog'
    ]
except ImportError:
    # Wenn PySide6 nicht verfügbar ist
    __all__ = [
        'EmailConfig',
        'email_config',
        'load_config_from_file',
        'EmailSender',
        'EmailService',
        'email_service',
        'EmailTemplate',
        'PlanNotificationTemplate',
        'AvailabilityRequestTemplate'
    ]
