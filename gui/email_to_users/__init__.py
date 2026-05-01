"""
GUI-Integration für die E-Mail-Funktionalität des HCC Plan-Projekts.

Dieses Paket enthält Dialoge zum Versand von Plan-Benachrichtigungen,
Verfügbarkeitsanfragen, benutzerdefinierten Mails und Bulk-Mails. Versand
läuft über die Web-API; SMTP-Konfiguration wird unter /admin/email-settings
im Web-UI gepflegt — der Desktop-Client hat keine eigene Konfiguration mehr.
"""

from .gui_integration_main import (
    show_plan_notification_dialog,
    show_availability_request_dialog,
    show_custom_email_dialog,
    show_bulk_email_dialog,
)

__all__ = [
    'show_plan_notification_dialog',
    'show_availability_request_dialog',
    'show_custom_email_dialog',
    'show_bulk_email_dialog',
]