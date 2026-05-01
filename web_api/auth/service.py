"""Auth-Service: Passwort-Hashing, JWT-Token-Verwaltung und User-Lookup."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from web_api.config import Settings
from web_api.models.web_models import WebUser

_ALGORITHM = "HS256"


# ── User-Lookup ───────────────────────────────────────────────────────────────


def normalize_email(email: str) -> str:
    """Email-Normalisierung für Login-Lookup: trimmen + lowercase."""
    return email.strip().lower()


def load_user_with_roles(session: Session, email: str) -> WebUser | None:
    """Lädt einen WebUser per Email mit eager-loaded Rollen."""
    return session.exec(
        select(WebUser)
        .where(WebUser.email == normalize_email(email))
        .options(selectinload(WebUser.role_links))  # type: ignore[arg-type]
    ).first()


# ── Passwort ──────────────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())


# ── JWT ───────────────────────────────────────────────────────────────────────


def create_access_token(
    user_id: str,
    email: str,
    roles: list[str],
    settings: Settings,
) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "roles": roles,  # Liste aller Rollen des Users
        "type": "access",
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def create_refresh_token(user_id: str, settings: Settings) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "type": "refresh", "iat": now, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str, settings: Settings) -> dict:
    """Wirft jwt.PyJWTError bei ungültigem oder abgelaufenem Token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])