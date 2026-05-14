"""Auth-Service: Passwort-Hashing, JWT-Token-Verwaltung und User-Lookup."""

from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy.orm import selectinload
from sqlmodel import Session, select

from web_api.config import Settings
from web_api.models.web_models import WebUser

_ALGORITHM = "HS256"

# Toleranz gegen Uhren-Drift bei iat-vs-password_changed_at-Vergleich (Sekunden).
_PWD_CHANGE_CLOCK_SKEW_SECONDS = 5

# Mindestabstand zwischen zwei `last_login_at`-Updates. Verhindert, dass
# jeder Silent-Refresh und jeder Browser-Tab eigene Writes auf die User-Zeile
# produziert — fuer die Benutzerverwaltung reicht Tages-Granularitaet voellig.
_LAST_LOGIN_DEBOUNCE_SECONDS = 24 * 60 * 60


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


# ── Login-Aktivitaet ──────────────────────────────────────────────────────────


def touch_last_login(session: Session, user: WebUser) -> bool:
    """Schreibt `last_login_at = now()`, wenn der letzte Wert > 24 h alt ist.

    Returns True, wenn ein Write geflusht wurde (Caller entscheidet ueber commit).
    Aufrufer: Login-Endpoint und Silent-Refresh. Idempotenter Tages-Heartbeat.
    """
    now = datetime.now(timezone.utc)
    if user.last_login_at is not None:
        last = user.last_login_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if (now - last).total_seconds() < _LAST_LOGIN_DEBOUNCE_SECONDS:
            return False
    user.last_login_at = now
    session.add(user)
    return True


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


# ── Silent-Refresh ────────────────────────────────────────────────────────────


def silent_refresh(
    refresh_token: str,
    session: Session,
    settings: Settings,
) -> tuple[WebUser, str, str] | None:
    """Validiert einen Refresh-Token und stellt ein neues Token-Paar aus.

    Gibt `(user, access, refresh)` zurück oder `None`, wenn der Token ungültig,
    abgelaufen, vom falschen Typ ist, der User inaktiv ist oder der Token vor
    der letzten Passwort-Änderung ausgestellt wurde (Reset/Self-Change revoziert
    alle Sessions).

    Wird sowohl von `/auth/refresh` (explizit, Desktop-Client) als auch von
    `require_login` (Browser-Silent-Refresh) verwendet — eine Stelle für die
    iat-vs-password_changed_at-Sicherheitsregel.

    Concurrency: Zwei parallele Requests mit abgelaufenem Access-Token werden
    beide erfolgreich refreshen und sich die Cookies gegenseitig überschreiben.
    Aktuell folgenlos (keine serverseitige Refresh-Allowlist) — bei Einführung
    eines solchen Registers würde das ein Race.
    """
    try:
        payload = decode_token(refresh_token, settings)
    except jwt.PyJWTError:
        return None

    if payload.get("type") != "refresh":
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    user = session.exec(
        select(WebUser)
        .where(WebUser.id == user_id)
        .options(selectinload(WebUser.role_links))  # type: ignore[arg-type]
    ).first()

    if not user or not user.is_active:
        return None

    token_iat = payload.get("iat")
    if token_iat is not None:
        pwd_changed = user.password_changed_at
        if pwd_changed.tzinfo is None:
            pwd_changed = pwd_changed.replace(tzinfo=timezone.utc)
        if token_iat + _PWD_CHANGE_CLOCK_SKEW_SECONDS < int(pwd_changed.timestamp()):
            return None

    role_values = [r.value for r in user.roles]
    new_access = create_access_token(str(user.id), user.email, role_values, settings)
    new_refresh = create_refresh_token(str(user.id), settings)

    # Tages-Heartbeat: ohne Refresh wuerde der Wert bei eingeloggten Browser-
    # Sessions nie wieder aktualisiert. Commit ueberlassen wir dem Caller.
    if touch_last_login(session, user):
        session.commit()

    return user, new_access, new_refresh