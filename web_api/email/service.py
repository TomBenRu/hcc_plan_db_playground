"""Email-Service: SMTP-Backend oder Console-Backend (für Entwicklung)."""

import logging
import smtplib
from dataclasses import dataclass, field
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


@dataclass
class EmailPayload:
    to: list[str]
    subject: str
    html_body: str
    cc: list[str] = field(default_factory=list)


def send_emails_background(payloads: list[EmailPayload], settings) -> None:
    """Hilfsfunktion für BackgroundTasks: sendet mehrere E-Mail-Payloads nacheinander."""
    for payload in payloads:
        send_email(
            payload,
            backend=settings.EMAIL_BACKEND,
            smtp_host=settings.SMTP_HOST,
            smtp_port=settings.SMTP_PORT,
            smtp_user=settings.SMTP_USER,
            smtp_password=settings.SMTP_PASSWORD,
            email_from=settings.EMAIL_FROM,
        )


def send_email(payload: EmailPayload, *, backend: str, smtp_host: str, smtp_port: int,
               smtp_user: str, smtp_password: str, email_from: str) -> None:
    """Versendet eine E-Mail. Für BackgroundTasks konzipiert (keine Session nötig).

    backend="console": Gibt die E-Mail nur als Log-Eintrag aus.
    backend="smtp":    Versendet via SMTP mit STARTTLS.
    """
    if backend == "console":
        recipients = ", ".join(payload.to)
        separator = "─" * 60
        print(f"\n{separator}")
        print(f"[EMAIL] To:      {recipients}")
        if payload.cc:
            print(f"[EMAIL] Cc:      {', '.join(payload.cc)}")
        print(f"[EMAIL] Subject: {payload.subject}")
        print(f"[EMAIL] Body:\n{payload.html_body}")
        print(f"{separator}\n")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = payload.subject
    msg["From"] = email_from
    msg["To"] = ", ".join(payload.to)
    if payload.cc:
        msg["Cc"] = ", ".join(payload.cc)
    msg.attach(MIMEText(payload.html_body, "html", "utf-8"))

    all_recipients = payload.to + payload.cc
    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.ehlo()
            server.starttls()
            if smtp_user:
                server.login(smtp_user, smtp_password)
            server.sendmail(email_from, all_recipients, msg.as_string())
    except Exception:
        logger.exception("E-Mail-Versand fehlgeschlagen (to=%s, subject=%s)", payload.to, payload.subject)
