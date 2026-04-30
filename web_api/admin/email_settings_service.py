"""Service: CRUD auf der email_settings-Singleton-Tabelle.

Singleton-Strategie: erste Zeile via LIMIT 1 lesen. Save legt sie an, falls
sie noch nicht existiert (UPSERT-Pattern), sonst Update der bestehenden Zeile.
project_id bleibt heute NULL — wenn später Multi-Tenant aktiviert wird, kommt
hier die Auswahl per project_id-Filter rein.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select as sa_select
from sqlmodel import Session

from web_api.email.crypto import encrypt
from web_api.models.web_models import EmailSettings


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_settings_or_none(session: Session) -> Optional[EmailSettings]:
    return session.execute(sa_select(EmailSettings).limit(1)).scalars().first()


def upsert_settings(
    session: Session,
    *,
    smtp_host: str,
    smtp_port: int,
    smtp_username: str,
    smtp_password: Optional[str],
    use_tls: bool,
    use_ssl: bool,
    email_from: str,
    email_from_name: Optional[str],
    updated_by_id: uuid.UUID,
) -> EmailSettings:
    """Speichert die Settings. Wenn smtp_password None oder "" ist, bleibt der
    bestehende verschlüsselte Wert unverändert ("leer = nicht ändern"-Pattern).
    """
    row = get_settings_or_none(session)
    if row is None:
        row = EmailSettings(
            smtp_host=smtp_host,
            smtp_port=smtp_port,
            smtp_username=smtp_username,
            smtp_password_encrypted=encrypt(smtp_password or ""),
            use_tls=use_tls,
            use_ssl=use_ssl,
            email_from=email_from,
            email_from_name=email_from_name,
            updated_by_id=updated_by_id,
        )
        session.add(row)
    else:
        row.smtp_host = smtp_host
        row.smtp_port = smtp_port
        row.smtp_username = smtp_username
        if smtp_password:
            row.smtp_password_encrypted = encrypt(smtp_password)
        row.use_tls = use_tls
        row.use_ssl = use_ssl
        row.email_from = email_from
        row.email_from_name = email_from_name
        row.updated_by_id = updated_by_id
        row.last_modified = _utcnow()
    session.commit()
    session.refresh(row)
    return row