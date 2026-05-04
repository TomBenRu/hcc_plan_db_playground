"""Passwort-Reset: Token-Erzeugung, -Verifikation und Email-Versand.

Tokens werden als Klartext (URL-safe) an den User gemailt; in der Datenbank
liegt nur der SHA-256-Hex-Digest. Damit ist der Token bei einem späteren
DB-Leak nicht direkt nutzbar (kurzlebiger Schaden) und gleichzeitig
deterministisch nachschlagbar.
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from web_api.auth.service import hash_password
from web_api.config import Settings
from web_api.email.service import EmailPayload
from web_api.models.web_models import PasswordResetToken, WebUser
from web_api.templating import templates

RESET_TOKEN_TTL_MINUTES = 60
EMAIL_THROTTLE_MINUTES = 5  # frühestens alle 5 Min eine neue Mail pro User


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def has_recent_token(session: Session, user_id) -> bool:
    """True, wenn der User in den letzten EMAIL_THROTTLE_MINUTES schon einen Token bekommen hat."""
    cutoff = _utcnow() - timedelta(minutes=EMAIL_THROTTLE_MINUTES)
    recent = session.exec(
        select(PasswordResetToken)
        .where(PasswordResetToken.web_user_id == user_id)
        .where(PasswordResetToken.created_at >= cutoff)
    ).first()
    return recent is not None


def create_reset_token(session: Session, user: WebUser) -> str:
    """Erzeugt ein neues Token, speichert nur den SHA-256-Hash, gibt den Klartext zurück."""
    token = secrets.token_urlsafe(32)  # ~256 Bit Entropie
    record = PasswordResetToken(
        web_user_id=user.id,
        token_hash=_hash_token(token),
        expires_at=_utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
    )
    session.add(record)
    session.flush()
    return token


def verify_token(session: Session, token: str) -> WebUser | None:
    """Prüft den Token, ohne ihn zu verbrauchen. Für GET /auth/reset-password."""
    record = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token))
    ).first()
    if record is None or record.used_at is not None:
        return None

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < _utcnow():
        return None

    return session.exec(
        select(WebUser)
        .where(WebUser.id == record.web_user_id)
        .options(selectinload(WebUser.role_links))  # type: ignore[arg-type]
    ).first()


def consume_token_and_set_password(
    session: Session, token: str, new_password: str
) -> WebUser | None:
    """Verifiziert + verbraucht den Token, setzt neues Passwort und stempelt password_changed_at.

    Invalidiert ALLE anderen unbenutzten Reset-Tokens desselben Users (defense in depth:
    falls der User mehrere Reset-Mails angefordert hat, werden alte Links wertlos).
    """
    record = session.exec(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == _hash_token(token))
    ).first()
    if record is None or record.used_at is not None:
        return None

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < _utcnow():
        return None

    user = session.get(WebUser, record.web_user_id)
    if user is None or not user.is_active:
        return None

    now = _utcnow()
    user.hashed_password = hash_password(new_password)
    user.password_changed_at = now
    user.last_modified = now
    record.used_at = now

    other_tokens = session.exec(
        select(PasswordResetToken)
        .where(PasswordResetToken.web_user_id == user.id)
        .where(PasswordResetToken.id != record.id)
        .where(PasswordResetToken.used_at.is_(None))  # type: ignore[union-attr]
    ).all()
    for t in other_tokens:
        t.used_at = now

    session.add(user)
    session.add(record)
    return user


def build_reset_email(
    user: WebUser,
    token: str,
    settings: Settings,
    *,
    recipient_first_name: str | None = None,
) -> EmailPayload:
    base_url = getattr(settings, "BASE_URL", "").rstrip("/") or "http://localhost:8000"
    reset_link = f"{base_url}/auth/reset-password?token={token}"
    html = templates.get_template("emails/password_reset.html").render(
        user_email=user.email,
        reset_link=reset_link,
        ttl_minutes=RESET_TOKEN_TTL_MINUTES,
        recipient_first_name=recipient_first_name or "",
    )
    return EmailPayload(
        to=[user.email],
        subject="Passwort zurücksetzen — hcc plan",
        html_body=html,
    )