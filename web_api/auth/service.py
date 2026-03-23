"""Auth-Service: Passwort-Hashing und JWT-Token-Verwaltung."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from web_api.config import Settings

_ALGORITHM = "HS256"


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
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "email": email,
        "roles": roles,  # Liste aller Rollen des Users
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def create_refresh_token(user_id: str, settings: Settings) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {"sub": user_id, "type": "refresh", "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=_ALGORITHM)


def decode_token(token: str, settings: Settings) -> dict:
    """Wirft jwt.PyJWTError bei ungültigem oder abgelaufenem Token."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[_ALGORITHM])