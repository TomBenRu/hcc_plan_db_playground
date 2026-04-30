"""Email-Service: SMTP-Versand auf Basis der DB-gepflegten Konfiguration.

Öffentliche API:
    schedule_emails(background_tasks, payloads, session)
        Hauptfunktion für Router. Lädt die SMTP-Config aus der DB einmal,
        übergibt sie als Frozen-Dataclass an einen BackgroundTask. Wirft
        EmailNotConfiguredError, falls payloads vorliegen und die Config
        unvollständig ist — der Fehler propagiert in den Handler, damit der
        Admin ihn sofort sieht (statt still im Background-Worker zu sterben).

    EmailPayload
        Dataclass mit to, subject, html_body, cc.

Privat:
    _send_emails_with_config / _send_email
        Versand-Mechanik, läuft im BackgroundTask ohne DB-Session.
"""

import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from fastapi import BackgroundTasks
from sqlmodel import Session

from web_api.email.config_loader import SmtpConfig, load_smtp_config

logger = logging.getLogger(__name__)


@dataclass
class EmailPayload:
    to: list[str]
    subject: str
    html_body: str
    cc: list[str] = field(default_factory=list)


def schedule_emails(
    background_tasks: BackgroundTasks,
    payloads: list[EmailPayload],
    session: Session,
) -> None:
    """Plant den Versand mehrerer E-Mails als BackgroundTask.

    Sicheres Verhalten gegenüber leerer Liste: keine DB-Abfrage, kein Task.
    Bei nicht-leerer Liste wird die SMTP-Config geladen und entschlüsselt;
    schlägt das fehl, propagiert die Exception in den Handler.
    """
    if not payloads:
        return
    smtp_config = load_smtp_config(session)
    background_tasks.add_task(_send_emails_with_config, payloads, smtp_config)


def _send_emails_with_config(payloads: list[EmailPayload], smtp_config: SmtpConfig) -> None:
    for payload in payloads:
        _send_email(payload, smtp_config)


def _send_email(payload: EmailPayload, smtp_config: SmtpConfig) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = payload.subject
    msg["From"] = smtp_config.from_header
    msg["To"] = ", ".join(payload.to)
    if payload.cc:
        msg["Cc"] = ", ".join(payload.cc)
    msg.attach(MIMEText(payload.html_body, "html", "utf-8"))

    all_recipients = payload.to + payload.cc
    try:
        if smtp_config.use_ssl:
            server_cls = smtplib.SMTP_SSL
        else:
            server_cls = smtplib.SMTP
        with server_cls(smtp_config.host, smtp_config.port, timeout=10) as server:
            server.ehlo()
            if smtp_config.use_tls and not smtp_config.use_ssl:
                server.starttls()
                server.ehlo()
            if smtp_config.username:
                server.login(smtp_config.username, smtp_config.password)
            server.sendmail(smtp_config.email_from, all_recipients, msg.as_string())
    except Exception:
        logger.exception(
            "E-Mail-Versand fehlgeschlagen (to=%s, subject=%s)",
            payload.to,
            payload.subject,
        )