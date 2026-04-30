"""Loader für SMTP-Konfiguration aus der DB.

Konvention: Loader wird im Router-Layer aufgerufen (nicht im BackgroundTask),
damit die DB-Session noch lebt und Konfigurationsfehler im Handler crashen —
nicht still im Background-Worker. Das Ergebnis ist eine immutable Frozen-
Dataclass, die sicher in BackgroundTasks weitergereicht werden kann.
"""

from dataclasses import dataclass

from sqlalchemy import select as sa_select
from sqlmodel import Session

from web_api.email.crypto import decrypt
from web_api.models.web_models import EmailSettings


class EmailNotConfiguredError(RuntimeError):
    """E-Mail-Versand wurde versucht, aber es liegen keine Settings vor.

    Die Admin-UI unter /admin/email-settings öffnen und SMTP-Daten eintragen.
    """


@dataclass(frozen=True)
class SmtpConfig:
    """Versand-fähige SMTP-Konfiguration. Passwort ist bereits entschlüsselt.

    Wird vom Router geladen und an Background-Tasks übergeben — frozen,
    damit klar ist, dass nachträgliche Mutation nicht erwartet wird.
    """

    host: str
    port: int
    username: str
    password: str
    use_tls: bool
    use_ssl: bool
    email_from: str
    email_from_name: str | None

    @property
    def from_header(self) -> str:
        """Liefert den `From`-Header inkl. Anzeigename, falls gesetzt."""
        if self.email_from_name:
            return f'"{self.email_from_name}" <{self.email_from}>'
        return self.email_from


def load_smtp_config(session: Session) -> SmtpConfig:
    """Lädt + entschlüsselt die SMTP-Konfiguration aus der DB.

    Heute Singleton (nimmt die erste Zeile). Wirft EmailNotConfiguredError,
    wenn keine Zeile existiert oder Pflichtfelder leer sind.
    """
    row = session.execute(sa_select(EmailSettings).limit(1)).scalars().first()
    if row is None:
        raise EmailNotConfiguredError(
            "E-Mail-Versand ist nicht konfiguriert. Admin-UI unter "
            "/admin/email-settings öffnen und SMTP-Server eintragen."
        )
    if not row.smtp_host or not row.email_from:
        raise EmailNotConfiguredError(
            "SMTP-Konfiguration ist unvollständig (host oder from-Adresse leer). "
            "/admin/email-settings öffnen und vervollständigen."
        )
    return SmtpConfig(
        host=row.smtp_host,
        port=row.smtp_port,
        username=row.smtp_username,
        password=decrypt(row.smtp_password_encrypted),
        use_tls=row.use_tls,
        use_ssl=row.use_ssl,
        email_from=row.email_from,
        email_from_name=row.email_from_name,
    )