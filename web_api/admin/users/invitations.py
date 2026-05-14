"""Einladungs-Flow: WebUser anlegen + Setup-Token + Setup-Mail.

Wir nutzen die bestehende `PasswordResetToken`-Tabelle. Einziger Unterschied
zum Reset: laengeres Expiry (7 Tage) und ein eigenes Mail-Template, das den
Empfaenger als 'neu eingeladen' anspricht. Eingeloest wird der Token beim
gleichen `/auth/reset-password`-Endpoint — der User merkt nicht, dass
intern dasselbe Token-Schema benutzt wird.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlmodel import Session, select

from database.models import Person
from web_api.auth.service import hash_password, normalize_email
from web_api.config import Settings
from web_api.email.service import EmailPayload
from web_api.email.validation import EmailDomainInvalid, validate_deliverable_email
from web_api.models.web_models import (
    PasswordResetToken,
    WebUser,
    WebUserRole,
    WebUserRoleLink,
)
from web_api.templating import templates

logger = logging.getLogger(__name__)

INVITATION_TOKEN_TTL_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_invitation(
    session: Session,
    *,
    actor: WebUser,
    email: str,
    roles: set[WebUserRole],
    person_id: uuid.UUID | None,
) -> tuple[WebUser, str]:
    """Legt einen neuen WebUser an und gibt den Klartext-Setup-Token zurueck.

    Wirft 409 bei vorhandenem Konto, 422 bei ungueltiger Adresse / leeren
    Rollen, 409 bei bereits verknuepfter Person.
    """
    if not roles:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Mindestens eine Rolle muss zugewiesen werden.",
        )

    norm_email = normalize_email(email)
    try:
        norm_email = validate_deliverable_email(norm_email)
    except EmailDomainInvalid as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"E-Mail-Adresse ist nicht zustellbar: {exc}",
        )

    existing = session.execute(
        select(WebUser).where(WebUser.email == norm_email)
    ).scalar_one_or_none()
    if existing is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Ein Konto mit dieser E-Mail existiert bereits.",
        )

    if person_id is not None:
        person = session.get(Person, person_id)
        if person is None or person.prep_delete is not None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                detail="Person nicht gefunden oder gelöscht.",
            )
        already_linked = session.execute(
            select(WebUser).where(WebUser.person_id == person_id)
        ).scalar_one_or_none()
        if already_linked is not None:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail=f"Diese Person ist bereits mit {already_linked.email} verknüpft.",
            )

    # Zufalls-Hash als initialer Passwort-Wert — der User wird ihn nie kennen,
    # der Setup-Token uebernimmt das Setzen des echten Passworts.
    initial_secret = secrets.token_urlsafe(32)
    user = WebUser(
        email=norm_email,
        person_id=person_id,
        hashed_password=hash_password(initial_secret),
        is_active=True,
    )
    session.add(user)
    session.flush()  # benoetigt user.id

    for role in roles:
        session.add(WebUserRoleLink(web_user_id=user.id, role=role))

    token_plain = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            web_user_id=user.id,
            token_hash=_hash_token(token_plain),
            expires_at=_utcnow() + timedelta(days=INVITATION_TOKEN_TTL_DAYS),
        )
    )
    session.commit()
    session.refresh(user)

    logger.info(
        "user_admin_action",
        extra={
            "action": "invite_user",
            "actor_id": str(actor.id),
            "target_id": str(user.id),
            "roles": [r.value for r in roles],
            "person_id": str(person_id) if person_id else None,
        },
    )
    return user, token_plain


def resend_invitation(
    session: Session,
    *,
    actor: WebUser,
    target_id: uuid.UUID,
) -> tuple[WebUser, str]:
    """Invalidiert offene Tokens und erzeugt einen neuen Setup-Link.

    Vermeidet, dass zwei gleichzeitig gueltige Links existieren — sonst koennte
    die alte Mail nachtraeglich ankommen und Verwirrung stiften.
    """
    user = session.get(WebUser, target_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Benutzer nicht gefunden")

    now = _utcnow()
    open_tokens = session.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.web_user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    ).scalars().all()
    for t in open_tokens:
        t.used_at = now

    token_plain = secrets.token_urlsafe(32)
    session.add(
        PasswordResetToken(
            web_user_id=user.id,
            token_hash=_hash_token(token_plain),
            expires_at=now + timedelta(days=INVITATION_TOKEN_TTL_DAYS),
        )
    )
    session.commit()
    session.refresh(user)

    logger.info(
        "user_admin_action",
        extra={
            "action": "resend_invitation",
            "actor_id": str(actor.id),
            "target_id": str(user.id),
        },
    )
    return user, token_plain


def build_invitation_email(
    user: WebUser,
    token: str,
    settings: Settings,
    *,
    inviter_name: str | None = None,
) -> EmailPayload:
    base_url = getattr(settings, "BASE_URL", "").rstrip("/") or "http://localhost:8000"
    setup_link = f"{base_url}/auth/reset-password?token={token}"
    html = templates.get_template("emails/user_invitation.html").render(
        user_email=user.email,
        setup_link=setup_link,
        ttl_days=INVITATION_TOKEN_TTL_DAYS,
        inviter_name=inviter_name or "",
    )
    return EmailPayload(
        to=[user.email],
        subject="Willkommen bei hcc plan — Passwort setzen",
        html_body=html,
    )
