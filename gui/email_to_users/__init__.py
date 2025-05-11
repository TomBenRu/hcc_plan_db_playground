"""
GUI-Integration für die E-Mail-Funktionalität des HCC Plan DB Playground-Projekts.

Dieses Paket enthält Dialoge und Funktionen zur Integration der E-Mail-Funktionalität
in die Qt-basierte Benutzeroberfläche.
"""

from .gui_integration_main import (
    show_config_dialog,
    show_plan_notification_dialog,
    show_availability_request_dialog,
    show_custom_email_dialog,
    show_bulk_email_dialog,
    load_email_config
)

__all__ = [
    'show_config_dialog',
    'show_plan_notification_dialog',
    'show_availability_request_dialog',
    'show_custom_email_dialog',
    'show_bulk_email_dialog',
    'load_email_config'
]