"""E-Mail-Versand-Pipeline (Plan-Notification, Verfügbarkeitsanfragen, Bulk).

Versand und SMTP-Konfiguration laufen über web_api/email/ — diese Module
liefern die Domain-Logik (Empfänger-Auflösung, Template-Rendering) und
die EmailService-Klasse, die mit einer SmtpConfig instantiiert wird.

Aufrufer (typisch web_api/desktop_api/email/router.py):

    from email_to_users.service import EmailService
    from web_api.email.config_loader import load_smtp_config
    service = EmailService(load_smtp_config(session))
    service.send_plan_notification(plan_id=..., recipient_ids=...)
"""

from .service import EmailService

__all__ = ["EmailService"]