"""
Paket für den E-Mail-Versand an Benutzer im HCC Plan DB Playground-Projekt.

Dieses Paket enthält Module für die Konfiguration, den E-Mail-Versand, Templates
und eine Service-Schicht für die Integration mit dem Datenmodell.
"""

from .config import EmailConfig, email_config, load_config_from_file
from .sender import EmailSender
from .service import EmailService, email_service
from .templates import EmailTemplate, PlanNotificationTemplate, AvailabilityRequestTemplate

# GUI-Integration (nur importieren, wenn PySide6 verfügbar ist)
try:
    from .gui_integration_main import (
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
