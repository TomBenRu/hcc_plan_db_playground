"""Login-Email-Wechsel mit Dual-Verify.

Flow:
  1. User triggert Wechsel → wir setzen pending_email, erzeugen Token,
     mailen Verify-Link an die NEUE Adresse + Hinweis an die ALTE.
  2. Der Klick auf den Verify-Link führt zu einer Bestätigungs-Seite (GET);
     erst der Submit (POST) verbraucht den Token und schaltet die Login-Email um.
  3. Andere Sessions bleiben aktiv: Tokens enthalten user.id, nicht email,
     der Wechsel revoziert keine bestehenden Refresh-Tokens. Bedrohungsmodell
     ist Stammdaten-Update, nicht Credential-Wechsel — wer eine Session-
     Übernahme befürchtet, nutzt den Passwort-Reset-Pfad (revoziert dort).
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from web_api.config import Settings
from web_api.email.service import EmailPayload
from web_api.models.web_models import EmailChangeToken, WebUser
from web_api.templating import templates

EMAIL_CHANGE_TOKEN_TTL_MINUTES = 60
EMAIL_THROTTLE_MINUTES = 5  # frühestens alle 5 Min eine neue Anfrage pro User


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def has_recent_token(session: Session, user_id) -> bool:
    """True, wenn der User in den letzten EMAIL_THROTTLE_MINUTES schon einen Token bekommen hat."""
    cutoff = _utcnow() - timedelta(minutes=EMAIL_THROTTLE_MINUTES)
    recent = session.exec(
        select(EmailChangeToken)
        .where(EmailChangeToken.web_user_id == user_id)
        .where(EmailChangeToken.created_at >= cutoff)
    ).first()
    return recent is not None


def is_email_taken_by_other(session: Session, target_email: str, user_id) -> bool:
    """Prüft, ob target_email bereits Login-Email eines ANDEREN aktiven WebUsers ist."""
    target = normalize_email(target_email)
    other = session.exec(
        select(WebUser).where(WebUser.email == target).where(WebUser.id != user_id)
    ).first()
    return other is not None


def create_email_change_token(
    session: Session, user: WebUser, target_email: str
) -> str:
    """Erzeugt ein neues Token, invalidiert vorhandene unbenutzte Tokens des Users.

    Setzt zusätzlich user.pending_email (rein informativ für die UI).
    """
    target = normalize_email(target_email)

    # Vorherige Wunsch-Tokens neutralisieren — sonst könnte ein altes Token einen
    # Wechsel auf eine nicht mehr gewünschte Adresse einleiten.
    now = _utcnow()
    open_tokens = session.exec(
        select(EmailChangeToken)
        .where(EmailChangeToken.web_user_id == user.id)
        .where(EmailChangeToken.used_at.is_(None))  # type: ignore[union-attr]
    ).all()
    for t in open_tokens:
        t.used_at = now
        session.add(t)

    token = secrets.token_urlsafe(32)
    record = EmailChangeToken(
        web_user_id=user.id,
        target_email=target,
        token_hash=_hash_token(token),
        expires_at=now + timedelta(minutes=EMAIL_CHANGE_TOKEN_TTL_MINUTES),
    )
    session.add(record)
    user.pending_email = target
    session.add(user)
    session.flush()
    return token


def verify_token(session: Session, token: str) -> tuple[WebUser, str] | None:
    """Read-only Verifikation. Liefert (user, target_email) oder None."""
    record = session.exec(
        select(EmailChangeToken).where(EmailChangeToken.token_hash == _hash_token(token))
    ).first()
    if record is None or record.used_at is not None:
        return None

    expires_at = record.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < _utcnow():
        return None

    user = session.exec(
        select(WebUser)
        .where(WebUser.id == record.web_user_id)
        .options(selectinload(WebUser.role_links))  # type: ignore[arg-type]
    ).first()
    if user is None or not user.is_active:
        return None

    return user, record.target_email


def consume_token(session: Session, token: str) -> tuple[WebUser, str, str] | None:
    """Verbraucht den Token, schaltet Login-Email um. Liefert (user, old_email, new_email).

    Race-sicher: prüft beim Verbrauch nochmal, ob target_email inzwischen von
    einem anderen User belegt wurde — gibt None zurück, falls ja.
    """
    record = session.exec(
        select(EmailChangeToken).where(EmailChangeToken.token_hash == _hash_token(token))
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

    if is_email_taken_by_other(session, record.target_email, user.id):
        return None

    now = _utcnow()
    old_email = user.email
    user.email = record.target_email
    user.pending_email = None
    user.last_modified = now
    record.used_at = now
    session.add(user)
    session.add(record)
    session.flush()
    return user, old_email, record.target_email


def cancel_pending_change(session: Session, user: WebUser) -> None:
    """Räumt offene Tokens auf und setzt pending_email zurück."""
    now = _utcnow()
    open_tokens = session.exec(
        select(EmailChangeToken)
        .where(EmailChangeToken.web_user_id == user.id)
        .where(EmailChangeToken.used_at.is_(None))  # type: ignore[union-attr]
    ).all()
    for t in open_tokens:
        t.used_at = now
        session.add(t)
    user.pending_email = None
    session.add(user)
    session.flush()


def build_verify_email(target_email: str, token: str, settings: Settings) -> EmailPayload:
    """Verifikations-Mail an die NEUE Adresse."""
    base_url = getattr(settings, "BASE_URL", "").rstrip("/") or "http://localhost:8000"
    confirm_link = f"{base_url}/account/email-change/confirm?token={token}"
    html = templates.get_template("emails/email_change_verify.html").render(
        target_email=target_email,
        confirm_link=confirm_link,
        ttl_minutes=EMAIL_CHANGE_TOKEN_TTL_MINUTES,
    )
    return EmailPayload(
        to=[target_email],
        subject="Bestätige deine neue E-Mail-Adresse — hcc plan",
        html_body=html,
    )


def build_notice_email(old_email: str, target_email: str, settings: Settings) -> EmailPayload:
    """Hinweis-Mail an die ALTE Adresse — passive Information, kein Stop-Link."""
    html = templates.get_template("emails/email_change_notice.html").render(
        old_email=old_email,
        target_email=target_email,
    )
    return EmailPayload(
        to=[old_email],
        subject="Hinweis: Anfrage zur Änderung deiner Login-Adresse — hcc plan",
        html_body=html,
    )